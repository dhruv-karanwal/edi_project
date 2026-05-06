from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, Dict, Any, List
import re
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from db.database import get_db
from db.models import Document, Conversation, Message
from api.models.request_models import QueryRequest
from api.models.response_models import QueryResponse, Evidence
from retrieval.vector_search import VectorSearch
from retrieval.graph_search import GraphSearch
from retrieval.hybrid_ranker import HybridRanker
from generation.query_classifier import QueryClassifier
from generation.answer_generator import AnswerGenerator
from config import get_settings

router = APIRouter(prefix="/api/query", tags=["query"])


def _contains_reference(text: str, label: str, number: str) -> bool:
    if not text:
        return False
    pattern = rf"\b{label}\.?(?:\s|\s*[:#\-]\s*){re.escape(number)}\b"
    return re.search(pattern, text.lower()) is not None


def _matches_explicit_reference(result: Dict[str, Any], classification: Dict[str, Any]) -> bool:
    figure_number = classification.get("figure_number")
    table_number = classification.get("table_number")

    text = " ".join([
        str(result.get("caption", "")),
        str(result.get("content", "")),
        str(result.get("section_title", "")),
    ]).lower()

    if figure_number:
        if result.get("chunk_type") != "figure":
            return False
        return _contains_reference(text, "fig(?:ure)?", str(figure_number))

    if table_number:
        if result.get("chunk_type") != "table":
            return False
        return _contains_reference(text, "table", str(table_number))

    return False


def _apply_reference_aware_ranking(
    ranked_results: List[Dict[str, Any]],
    classification: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Boost exact Figure/Table references to reduce cross-figure confusion."""
    if not (classification.get("figure_number") or classification.get("table_number")):
        return ranked_results

    for result in ranked_results:
        if _matches_explicit_reference(result, classification):
            result["relevance_score"] *= 1.8
            result["reference_match"] = True
        elif classification.get("figure_number") and result.get("chunk_type") == "figure":
            result["relevance_score"] *= 0.75
            result["reference_match"] = False
        elif classification.get("table_number") and result.get("chunk_type") == "table":
            result["relevance_score"] *= 0.75
            result["reference_match"] = False

    ranked_results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
    return ranked_results


def _is_usable_figure_image(image_path: Optional[str]) -> bool:
    """Filter out invalid or mostly-black figure artifacts for cleaner UI evidence."""
    if not image_path:
        return False

    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return False

    try:
        with Image.open(path) as img:
            gray = img.convert("L")
            stat = gray.getextrema()
            if not stat:
                return False

            min_px, max_px = stat
            if max_px <= 8:
                return False

            histogram = gray.histogram()
            total = sum(histogram) or 1
            very_dark = sum(histogram[:8])
            dark_ratio = very_dark / total

            if dark_ratio > 0.985:
                return False

            return True
    except (OSError, UnidentifiedImageError, ValueError):
        return False

@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """Ask a question about a document."""

    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    # Verify document exists and is ready
    document = db.query(Document).filter(Document.id == request.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready (status: {document.status})"
        )
    
    # Get or create conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.document_id != request.document_id:
            raise HTTPException(
                status_code=400,
                detail="Conversation does not belong to the specified document"
            )
    else:
        conversation = Conversation(document_id=request.document_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    settings = get_settings()

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.question
    )
    db.add(user_message)
    db.commit()
    
    try:
        # Step 1: Classify query
        classifier = QueryClassifier()
        classification = classifier.classify(request.question)
        
        # Step 2: Vector search
        vector_search = VectorSearch()
        vector_results = vector_search.search(
            query=request.question,
            document_id=str(request.document_id),
            chunk_types=classification['preferred_types']
        )
        
        # Step 3: Graph search
        if vector_results:
            graph_search = GraphSearch(str(request.document_id))
            seed_ids = [r['chunk_id'] for r in vector_results[:3]]
            graph_neighbors = graph_search.get_graph_neighbors(seed_ids)
            
            # Expand with captions for figures/tables
            graph_neighbors = graph_search.expand_with_captions(graph_neighbors)
        else:
            graph_neighbors = []
        
        # Step 4: Hybrid ranking
        ranker = HybridRanker(db)
        ranked_results = ranker.merge_and_rank(vector_results, graph_neighbors)
        
        # Prioritize by query type
        if classification['preferred_types']:
            ranked_results = ranker.prioritize_by_type(
                ranked_results,
                classification['preferred_types']
            )

        ranked_results = _apply_reference_aware_ranking(ranked_results, classification)
        
        # Step 5: Select evidence used for answer generation + UI rendering
        filtered_results = [
            result for result in ranked_results
            if result.get('relevance_score', 0.0) >= settings.min_evidence_relevance
        ]

        if not filtered_results and ranked_results:
            # Ensure at least one evidence item when retrieval produced results.
            filtered_results = ranked_results[:1]

        if classification.get("figure_number") or classification.get("table_number"):
            exact_matches = [
                result for result in filtered_results
                if _matches_explicit_reference(result, classification)
            ]
            if exact_matches:
                contextual_text = [
                    result for result in filtered_results
                    if result.get("chunk_type") == "text"
                ]
                filtered_results = exact_matches + contextual_text

        answer_evidence = filtered_results[:settings.max_evidence_per_answer]

        # Step 6: Generate answer from exactly the same evidence set shown in UI
        generator = AnswerGenerator()
        answer = generator.generate_answer(
            request.question,
            answer_evidence,
            classification
        )

        evidence_list = []
        for result in answer_evidence:
            has_usable_image = _is_usable_figure_image(result.get('image_path'))
            evidence_list.append(Evidence(
                chunk_id=UUID(result['chunk_id']),
                chunk_type=result['chunk_type'],
                page_number=result['page_number'],
                section_title=result.get('section_title'),
                snippet=result['content'][:300],
                image_url=f"/api/documents/{request.document_id}/figure/{result['chunk_id']}" 
                    if has_usable_image else None,
                relevance_score=result['relevance_score']
            ))
        
        # Save assistant message
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            evidence=[ev.model_dump(mode="json") for ev in evidence_list]
        )
        db.add(assistant_message)
        db.commit()
        
        return QueryResponse(
            answer=answer,
            conversation_id=conversation.id,
            evidence=evidence_list
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db)
):
    """Get conversation history."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()
    
    return {
        "conversation_id": conversation.id,
        "document_id": conversation.document_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "evidence": msg.evidence,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
    }


@router.get("/documents/{document_id}/latest-conversation")
async def get_latest_conversation_for_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """Get the most recent conversation history for a document."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    conversation = db.query(Conversation).filter(
        Conversation.document_id == document_id
    ).order_by(Conversation.created_at.desc()).first()

    if not conversation:
        return {
            "conversation_id": None,
            "document_id": document_id,
            "messages": []
        }

    messages = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at).all()

    return {
        "conversation_id": conversation.id,
        "document_id": conversation.document_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "evidence": msg.evidence,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
    }


@router.get("/documents/{document_id}/conversations")
async def get_document_conversations(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """List all conversations for a document (newest first)."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    conversation_rows = (
        db.query(
            Conversation.id,
            Conversation.created_at,
            func.count(Message.id).label("message_count"),
            func.max(Message.created_at).label("last_message_at")
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .filter(Conversation.document_id == document_id)
        .group_by(Conversation.id, Conversation.created_at)
        .order_by(func.max(Message.created_at).desc().nullslast(), Conversation.created_at.desc())
        .all()
    )

    return {
        "document_id": document_id,
        "conversations": [
            {
                "conversation_id": row.id,
                "created_at": row.created_at,
                "message_count": row.message_count,
                "last_message_at": row.last_message_at,
            }
            for row in conversation_rows
        ]
    }