import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from models.db_models import get_db, Document, Chunk
from models.schemas import DocumentSchema, ChunkSchema, DocumentLayoutResponse, LayoutRegion
from services.pdf_service import PDFService
from vector_db.faiss_db import FAISSIndex
from config import get_settings
from utils.logger import logger

router   = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()
pdf_service = PDFService()


@router.get("", response_model=List[DocumentSchema])
async def list_documents(db: Session = Depends(get_db)):
    """Returns all documents in the workspace, ordered by most recent first."""
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentSchema)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """Retrieves metadata for a single document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/chunks", response_model=List[ChunkSchema])
async def get_chunks(
    document_id: str,
    chunk_type: Optional[str] = None,
    page:       Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Retrieves extracted structure chunks, filterable by type or page number."""
    query = db.query(Chunk).filter(Chunk.document_id == document_id)
    if chunk_type:
        query = query.filter(Chunk.chunk_type == chunk_type)
    if page:
        query = query.filter(Chunk.page_number == page)

    chunks = query.order_by(Chunk.page_number, Chunk.id).all()

    response_chunks = []
    for c in chunks:
        bbox_data = None
        if c.bbox:
            bbox_data = {
                "x0": float(c.bbox.get("x0", 0)),
                "y0": float(c.bbox.get("y0", 0)),
                "x1": float(c.bbox.get("x1", 0)),
                "y1": float(c.bbox.get("y1", 0)),
            }
        response_chunks.append(
            ChunkSchema(
                id                = c.id,
                chunk_type        = c.chunk_type,
                content           = c.content,
                page_number       = c.page_number,
                section_title     = c.section_title,
                caption           = c.caption,
                image_path        = c.image_path,
                bbox              = bbox_data,
                layout_label      = c.layout_label,
                layout_confidence = c.layout_confidence,
            )
        )
    return response_chunks


# ── v2.0 NEW: AI Layout Regions Endpoint ─────────────────────────────────────

@router.get("/{document_id}/layout", response_model=DocumentLayoutResponse)
async def get_document_layout(document_id: str, db: Session = Depends(get_db)):
    """
    Returns all AI-detected layout regions for a document.

    Used by the frontend to display detected region overlays on page images.
    Only chunks with a bounding box are included.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id, Chunk.bbox.isnot(None))
        .order_by(Chunk.page_number, Chunk.id)
        .all()
    )

    regions = []
    for c in chunks:
        bbox_data = None
        if c.bbox:
            bbox_data = {
                "x0": float(c.bbox.get("x0", 0)),
                "y0": float(c.bbox.get("y0", 0)),
                "x1": float(c.bbox.get("x1", 0)),
                "y1": float(c.bbox.get("y1", 0)),
            }
        regions.append(
            LayoutRegion(
                chunk_id          = c.id,
                chunk_type        = c.chunk_type,
                layout_label      = c.layout_label,
                layout_confidence = c.layout_confidence,
                page_number       = c.page_number,
                bbox              = bbox_data,
                content_preview   = c.content[:120] if c.content else "",
            )
        )

    return DocumentLayoutResponse(
        document_id = document_id,
        regions     = regions,
        total_count = len(regions),
    )


@router.delete("/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """
    Permanently deletes a document and all associated data:
      - Uploaded PDF file
      - Rendered page images
      - Cropped figure images
      - FAISS text index
      - FAISS CLIP visual index     (v2.0)
      - FAISS LayoutLMv3 index      (v2.0)
      - BM25 keyword index          (v2.0)
      - SQLite rows (cascaded)
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    logger.info(f"Initiating full deletion for document: {doc.filename}")

    # ── Clean up uploaded and rendered files ──────────────────────────────────
    try:
        for ext in [".pdf", ".png", ".jpg", ".jpeg"]:
            up_file = os.path.join(settings.uploads_dir, f"{document_id}{ext}")
            if os.path.exists(up_file):
                os.remove(up_file)

        base_name = os.path.splitext(doc.filename)[0]
        for folder, prefix in [
            (settings.pages_dir,   f"{base_name}_page_"),
            (settings.figures_dir, f"{document_id}_"),
        ]:
            if os.path.exists(folder):
                for file in os.listdir(folder):
                    if file.startswith(prefix):
                        os.remove(os.path.join(folder, file))

    except Exception as fe:
        logger.error(f"Error cleaning up document files: {fe}")

    # ── Clean up all FAISS indexes ────────────────────────────────────────────
    for suffix in ["", "_clip", "_layoutlm"]:
        FAISSIndex(document_id, suffix=suffix).delete()

    # ── Clean up BM25 index ───────────────────────────────────────────────────
    from rag.retriever import _bm25_path
    bm25_path = _bm25_path(document_id)
    if os.path.exists(bm25_path):
        try:
            os.remove(bm25_path)
        except Exception as e:
            logger.error(f"Failed to delete BM25 index: {e}")

    # ── Cascade-delete all DB rows ────────────────────────────────────────────
    db.delete(doc)
    db.commit()

    logger.info(f"Successfully deleted document: {document_id}")
    return {"message": "Document and all associated indexes deleted successfully."}


@router.get("/{document_id}/figure/{chunk_id}")
async def get_figure_image(
    document_id: str,
    chunk_id:    str,
    db: Session = Depends(get_db)
):
    """
    Dynamically crop and serve a visual document region on-demand.

    The crop PNG is cached in storage/figures/ after first generation.
    """
    chunk = (
        db.query(Chunk)
        .filter(Chunk.id == chunk_id, Chunk.document_id == document_id)
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    if chunk.chunk_type not in ("figure", "table") or not chunk.bbox:
        raise HTTPException(status_code=400, detail="Chunk is not a visual component.")

    crop_filename = f"{document_id}_{chunk_id}.png"
    crop_path     = os.path.join(settings.figures_dir, crop_filename)

    if not os.path.exists(crop_path):
        if not chunk.image_path or not os.path.exists(chunk.image_path):
            raise HTTPException(status_code=404, detail="Parent page image missing.")

        logger.info(f"Generating visual crop on-demand for chunk: {chunk_id}")
        success = pdf_service.crop_region(chunk.image_path, chunk.bbox, crop_path)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to render visual crop.")

    return FileResponse(crop_path, media_type="image/png")
