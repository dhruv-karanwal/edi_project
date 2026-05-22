import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import datetime
from models.db_models import get_db, Conversation, Message, Chunk
from models.schemas import QueryRequest, QueryResponse, ConversationSchema, MessageSchema, DocumentConversationsResponse, ConversationSummary, Evidence
from services.gemini_service import GeminiService
from services.pdf_service import PDFService
from rag.retriever import Retriever
from config import get_settings
from utils.logger import logger

router = APIRouter(prefix="/api/query", tags=["query"])
settings = get_settings()
gemini_service = GeminiService()
pdf_service = PDFService()
retriever = Retriever()

@router.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest, db: Session = Depends(get_db)):
    """Core grounded QA engine. Performs RAG semantic search, dynamic visual cropping, and invokes Gemini."""
    document_id = request.document_id
    question = request.question
    conversation_id = request.conversation_id

    # 1. Retrieve RAG semantic context
    try:
        logger.info(f"Retrieving semantic context for query: '{question}' on document {document_id}")
        evidence_list = retriever.retrieve_context(db, document_id, question, top_k=settings.top_k_vector)
    except Exception as e:
        logger.error(f"RAG context retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval engine failure: {e}")

    # Filter out evidence blocks below the minimum relevance threshold
    evidence_list = [ev for ev in evidence_list if ev["relevance_score"] >= settings.min_evidence_relevance]
    # Ensure we don't exceed max count
    evidence_list = evidence_list[:settings.top_k_vector]

    # 2. Gather visual crops for retrieved figures/tables (up to 3 to optimize tokens)
    crop_paths = []
    visual_evidence_count = 0
    
    for ev in evidence_list:
        if ev["chunk_type"] in ["figure", "table"] and visual_evidence_count < 3:
            chunk_id = ev["chunk_id"]
            chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
            
            if chunk and chunk.bbox and chunk.image_path:
                crop_filename = f"{document_id}_{chunk_id}.png"
                crop_path = os.path.join(settings.figures_dir, crop_filename)
                
                # Render crop image on the fly if it does not exist
                if not os.path.exists(crop_path):
                    logger.info(f"Generating visual crop on-the-fly for RAG injection: {chunk_id}")
                    pdf_service.crop_region(chunk.image_path, chunk.bbox, crop_path)
                
                if os.path.exists(crop_path):
                    crop_paths.append(crop_path)
                    visual_evidence_count += 1

    # 3. Retrieve or create Conversation session
    if not conversation_id:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            document_id=document_id
        )
        db.add(conversation)
        db.commit()
        conversation_id = conversation.id
        logger.info(f"Created new conversation session: {conversation_id}")
    else:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            # Fallback if invalid ID passed
            conversation = Conversation(
                id=str(uuid.uuid4()),
                document_id=document_id
            )
            db.add(conversation)
            db.commit()
            conversation_id = conversation.id

    # 4. Construct conversational memory history
    db_messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    chat_history = [{"role": msg.role, "content": msg.content} for msg in db_messages]

    # Limit memory window to the last 6 turns (12 messages) to prevent context bloat
    chat_history = chat_history[-12:]

    # 5. Invoke Google Gemini Vision API for grounded multimodal response
    try:
        answer = gemini_service.generate_answer(
            question=question,
            evidence=evidence_list,
            chat_history=chat_history,
            crop_image_paths=crop_paths
        )
    except Exception as gemini_err:
        logger.error(f"Gemini generation error: {gemini_err}")
        answer = f"Error: Generative AI reasoning failed. Please verify your Gemini API key. Details: {gemini_err}"

    # 6. Save User message and Assistant response to database
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=question
    )
    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        evidence=evidence_list
    )
    db.add(user_msg)
    db.add(assistant_msg)
    db.commit()

    # Format evidence models — v2.0 includes hybrid retrieval metadata
    response_evidence = []
    for ev in evidence_list:
        response_evidence.append(
            Evidence(
                chunk_id         = ev["chunk_id"],
                chunk_type       = ev["chunk_type"],
                page_number      = ev["page_number"],
                section_title    = ev.get("section_title"),
                snippet          = ev["snippet"],
                image_url        = ev.get("image_url"),
                relevance_score  = ev["relevance_score"],
                # v2.0 hybrid retrieval metadata
                retrieval_source = ev.get("retrieval_source"),
                layout_label     = ev.get("layout_label"),
                bm25_score       = ev.get("bm25_score"),
                faiss_score      = ev.get("faiss_score"),
                clip_score       = ev.get("clip_score"),
            )
        )

    return QueryResponse(
        answer          = answer,
        conversation_id = conversation_id,
        evidence        = response_evidence
    )

@router.get("/conversations/{conversation_id}", response_model=ConversationSchema)
async def get_messages(conversation_id: str, db: Session = Depends(get_db)):
    """Returns the complete message history for a conversation."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation session not found")

    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    
    response_messages = []
    for m in messages:
        evidence_data = None
        if m.evidence:
            evidence_data = []
            for ev in m.evidence:
                evidence_data.append(
                    Evidence(
                        chunk_id         = ev["chunk_id"],
                        chunk_type       = ev["chunk_type"],
                        page_number      = ev["page_number"],
                        section_title    = ev.get("section_title"),
                        snippet          = ev["snippet"],
                        image_url        = ev.get("image_url"),
                        relevance_score  = ev["relevance_score"],
                        retrieval_source = ev.get("retrieval_source"),
                        layout_label     = ev.get("layout_label"),
                        bm25_score       = ev.get("bm25_score"),
                        faiss_score      = ev.get("faiss_score"),
                        clip_score       = ev.get("clip_score"),
                    )
                )
        response_messages.append(
            MessageSchema(
                role=m.role,
                content=m.content,
                evidence=evidence_data,
                created_at=m.created_at
            )
        )

    return ConversationSchema(
        conversation_id=conversation.id,
        document_id=conversation.document_id,
        messages=response_messages
    )

@router.get("/documents/{document_id}/latest-conversation", response_model=ConversationSchema)
async def get_latest_conversation(document_id: str, db: Session = Depends(get_db)):
    """Recovers the most recent chat session for a document to restore UI state."""
    conversation = db.query(Conversation).filter(Conversation.document_id == document_id).order_by(Conversation.created_at.desc()).first()
    
    if not conversation:
        return ConversationSchema(
            conversation_id=None,
            document_id=document_id,
            messages=[]
        )

    return await get_messages(conversation.id, db)

@router.get("/documents/{document_id}/conversations", response_model=DocumentConversationsResponse)
async def list_conversations(document_id: str, db: Session = Depends(get_db)):
    """Lists all past conversations for a specific document with turns count summaries."""
    conversations = db.query(Conversation).filter(Conversation.document_id == document_id).order_by(Conversation.created_at.desc()).all()
    
    summaries = []
    for conv in conversations:
        # Count messages
        msg_count = db.query(Message).filter(Message.conversation_id == conv.id).count()
        last_msg = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).first()
        
        summaries.append(
            ConversationSummary(
                conversation_id=conv.id,
                created_at=conv.created_at,
                message_count=msg_count,
                last_message_at=last_msg.created_at if last_msg else None
            )
        )

    return DocumentConversationsResponse(
        document_id=document_id,
        conversations=summaries
    )
