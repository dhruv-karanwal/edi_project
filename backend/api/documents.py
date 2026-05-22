import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from models.db_models import get_db, Document, Chunk
from models.schemas import DocumentSchema, ChunkSchema
from services.pdf_service import PDFService
from vector_db.faiss_db import FAISSIndex
from config import get_settings
from utils.logger import logger

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()
pdf_service = PDFService()

@router.get("", response_model=List[DocumentSchema])
async def list_documents(db: Session = Depends(get_db)):
    """Returns all documents uploaded to the intelligence workspace."""
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return documents

@router.get("/{document_id}", response_model=DocumentSchema)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """Retrieves metadata of a single document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/{document_id}/chunks", response_model=List[ChunkSchema])
async def get_chunks(
    document_id: str,
    chunk_type: Optional[str] = None,
    page: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Retrieves extracted structure chunks. Filterable by type or page."""
    query = db.query(Chunk).filter(Chunk.document_id == document_id)
    if chunk_type:
        query = query.filter(Chunk.chunk_type == chunk_type)
    if page:
        query = query.filter(Chunk.page_number == page)
        
    chunks = query.order_by(Chunk.page_number, Chunk.id).all()
    
    # Map coordinate dictionary to Pydantic BoundingBox schema structure if present
    response_chunks = []
    for c in chunks:
        bbox_data = None
        if c.bbox:
            bbox_data = {
                "x0": float(c.bbox.get("x0", 0)),
                "y0": float(c.bbox.get("y0", 0)),
                "x1": float(c.bbox.get("x1", 0)),
                "y1": float(c.bbox.get("y1", 0))
            }
        response_chunks.append(
            ChunkSchema(
                id=c.id,
                chunk_type=c.chunk_type,
                content=c.content,
                page_number=c.page_number,
                section_title=c.section_title,
                caption=c.caption,
                image_path=c.image_path,
                bbox=bbox_data
            )
        )
    return response_chunks

@router.delete("/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Permanently deletes document, relational entries, files, and vector indices."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    logger.info(f"Initiating full deletion for document: {doc.filename}")

    # 1. Clean up local files
    try:
        # Delete original uploaded PDF/image file
        exts = [".pdf", ".png", ".jpg", ".jpeg"]
        for ext in exts:
            up_file = os.path.join(settings.uploads_dir, f"{document_id}{ext}")
            if os.path.exists(up_file):
                os.remove(up_file)
                logger.info(f"Deleted source file: {up_file}")

        # Delete page images associated with this document
        if os.path.exists(settings.pages_dir):
            for file in os.listdir(settings.pages_dir):
                if file.startswith(f"{document_id}_page_") or file.startswith(f"{os.path.splitext(doc.filename)[0]}_page_"):
                    os.remove(os.path.join(settings.pages_dir, file))

        # Delete cropped figures
        if os.path.exists(settings.figures_dir):
            for file in os.listdir(settings.figures_dir):
                if file.startswith(f"{document_id}_"):
                    os.remove(os.path.join(settings.figures_dir, file))
    except Exception as fe:
        logger.error(f"Error clean up document files: {fe}")

    # 2. Clean up FAISS Vector files
    faiss_index = FAISSIndex(document_id)
    faiss_index.delete()

    # 3. Clean up Database relationships (Cascade rule handles children)
    db.delete(doc)
    db.commit()
    
    logger.info(f"Successfully deleted document: {document_id}")
    return {"message": "Document deleted successfully"}

@router.get("/{document_id}/figure/{chunk_id}")
async def get_figure_image(document_id: str, chunk_id: str, db: Session = Depends(get_db)):
    """Dynamically crops and serves visual document figure regions on-demand."""
    chunk = db.query(Chunk).filter(Chunk.id == chunk_id, Chunk.document_id == document_id).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    if chunk.chunk_type not in ["figure", "table"] or not chunk.bbox:
        raise HTTPException(status_code=400, detail="Requested chunk is not a valid visual component.")

    # Target output path for cropped figure
    crop_filename = f"{document_id}_{chunk_id}.png"
    crop_path = os.path.join(settings.figures_dir, crop_filename)

    # If crop doesn't exist, create it on the fly
    if not os.path.exists(crop_path):
        page_image_path = chunk.image_path
        if not page_image_path or not os.path.exists(page_image_path):
            raise HTTPException(status_code=404, detail="Parent page image file missing. Cannot crop region.")
        
        logger.info(f"Generating visual grounding crop on-the-fly for chunk: {chunk_id}")
        success = pdf_service.crop_region(page_image_path, chunk.bbox, crop_path)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to render grounded visual crop.")

    return FileResponse(crop_path, media_type="image/png")
