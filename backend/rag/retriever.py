import os
import numpy as np
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from config import get_settings
from utils.logger import logger
from models.db_models import Chunk
from vector_db.faiss_db import FAISSIndex

settings = get_settings()

class Retriever:
    """Manages text chunking, SentenceTransformer vector embeddings, and semantic RAG retrieval."""
    
    def __init__(self):
        self._embedder = None
        self.dimension = 384  # Default for all-MiniLM-L6-v2

    def _get_embedder(self) -> SentenceTransformer:
        """Lazy initialization of SentenceTransformer model."""
        if self._embedder is None:
            logger.info(f"Loading SentenceTransformer model: {settings.embedding_model} on device: {settings.embedding_device}...")
            self._embedder = SentenceTransformer(
                settings.embedding_model,
                device=settings.embedding_device
            )
            # Fetch model dimension
            self.dimension = self._embedder.get_sentence_embedding_dimension()
            logger.info(f"Loaded embedder with feature dimension: {self.dimension}")
        return self._embedder

    def index_document_chunks(self, db: Session, document_id: str, raw_chunks: List[Dict[str, Any]]):
        """
        Takes layout chunks, saves them to SQLite database, embeds text, and indexes in local FAISS.
        """
        if not raw_chunks:
            logger.warning(f"No chunks extracted to index for document: {document_id}")
            return

        embedder = self._get_embedder()
        
        # 1. Extract texts to embed. Fall back to chunk content.
        texts_to_embed = []
        for chunk in raw_chunks:
            # Boost embeddings context by appending titles/metadata
            text = chunk["content"]
            if chunk.get("section_title"):
                text = f"Section: {chunk['section_title']}\n{text}"
            if chunk.get("caption"):
                text = f"Caption: {chunk['caption']}\n{text}"
            texts_to_embed.append(text)

        logger.info(f"Generating embeddings for {len(texts_to_embed)} chunks...")
        embeddings = embedder.encode(
            texts_to_embed,
            batch_size=settings.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        # 2. Save Chunks to SQL Database
        db_chunks = []
        chunk_uuids = []
        for idx, rc in enumerate(raw_chunks):
            db_chunk = Chunk(
                document_id=document_id,
                chunk_type=rc["chunk_type"],
                content=rc["content"],
                page_number=rc["page_number"],
                section_title=rc.get("section_title"),
                caption=rc.get("caption"),
                image_path=rc.get("image_path"),
                bbox=rc.get("bbox")
            )
            db.add(db_chunk)
            db_chunks.append(db_chunk)
            
        db.commit()
        # Retrieve UUIDs assigned by db models
        for chunk in db_chunks:
            chunk_uuids.append(chunk.id)

        # 3. Add Vectors to FAISS Index
        faiss_index = FAISSIndex(document_id, dimension=self.dimension)
        faiss_index.add_vectors(embeddings, chunk_uuids)
        logger.info(f"Indexed {len(chunk_uuids)} chunks in local database and FAISS index.")

    def retrieve_context(self, db: Session, document_id: str, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Searches FAISS, fetches matching SQL Chunks, and formats the output.
        """
        if top_k is None:
            top_k = settings.top_k_vector
            
        embedder = self._get_embedder()
        query_vector = embedder.encode(query, convert_to_numpy=True)
        
        # Query FAISS
        faiss_index = FAISSIndex(document_id, dimension=self.dimension)
        matches = faiss_index.search(query_vector, top_k=top_k)
        
        if not matches:
            return []
            
        # Match chunks by UUID in database
        chunk_ids = [uuid for uuid, score in matches]
        scores_map = {uuid: score for uuid, score in matches}
        
        db_chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
        
        # Sort chunks in order of scores returned by FAISS search
        db_chunks.sort(key=lambda c: chunk_ids.index(c.id))
        
        evidence = []
        for chunk in db_chunks:
            score = scores_map.get(chunk.id, 0.0)
            
            # Map standard figure server urls if visual chunk contains an image
            image_url = None
            if chunk.chunk_type in ["figure", "table"] and chunk.image_path:
                # Returns relative route which the frontend can append to its base URL
                image_url = f"http://localhost:8000/api/documents/{document_id}/figure/{chunk.id}"

            # Format the output matching Pydantic Evidence schema
            evidence.append({
                "chunk_id": chunk.id,
                "chunk_type": chunk.chunk_type,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "snippet": chunk.content,
                "image_url": image_url,
                "relevance_score": float(score),
                "bbox": chunk.bbox
            })
            
        return evidence
