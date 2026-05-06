from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from db.database import get_db
from db.models import Document, Chunk
from api.models.response_models import DocumentResponse, ChunkResponse
from file_storage.file_store import FileStore

router = APIRouter(prefix="/api/documents", tags=["documents"])

file_store = FileStore()

@router.get("", response_model=list[DocumentResponse])
async def list_documents(db: Session = Depends(get_db)):
    """List all documents."""
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return [DocumentResponse.from_orm(doc) for doc in documents]

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID, db: Session = Depends(get_db)):
    """Get document details."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.from_orm(document)

@router.get("/{document_id}/chunks", response_model=list[ChunkResponse])
async def get_chunks(
    document_id: UUID,
    chunk_type: Optional[str] = None,
    page: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get chunks for a document with optional filters."""
    query = db.query(Chunk).filter(Chunk.document_id == document_id)
    
    if chunk_type:
        query = query.filter(Chunk.chunk_type == chunk_type)
    
    if page:
        query = query.filter(Chunk.page_number == page)
    
    chunks = query.order_by(Chunk.chunk_index).all()
    return [ChunkResponse.from_orm(chunk) for chunk in chunks]

@router.get("/{document_id}/figure/{chunk_id}")
async def get_figure(
    document_id: UUID,
    chunk_id: UUID,
    db: Session = Depends(get_db)
):
    """Get figure image."""
    chunk = db.query(Chunk).filter(
        Chunk.id == chunk_id,
        Chunk.document_id == document_id,
        Chunk.chunk_type == 'figure'
    ).first()
    
    if not chunk or not chunk.image_path:
        raise HTTPException(status_code=404, detail="Figure not found")
    
    return FileResponse(chunk.image_path)

@router.delete("/{document_id}")
async def delete_document(document_id: UUID, db: Session = Depends(get_db)):
    """Delete a document and all its data."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from vector DB
    from retrieval.vector_search import VectorSearch
    vector_search = VectorSearch()
    vector_search.delete_document_chunks(str(document_id))
    
    # Delete files
    file_store.delete_document_files(str(document_id))
    
    # Delete from DB (cascades to chunks, conversations, messages)
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}