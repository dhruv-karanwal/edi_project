import os
import shutil
import uuid
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from models.db_models import get_db, Document
from models.schemas import UploadResponse, DocumentSchema
from services.pdf_service import PDFService
from rag.retriever import Retriever
from utils.logger import logger
from config import get_settings

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])
settings = get_settings()
pdf_service = PDFService()
retriever = Retriever()

def process_document_pipeline(document_id: str, file_path: str, db_session_factory):
    """
    Heavy ingestion pipeline run in a background thread.
    Parses PDF, renders pages, performs OCR fallback, extracts figures, embeds and indexes in FAISS.
    """
    db: Session = db_session_factory()
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        logger.error(f"Document {document_id} not found in database.")
        db.close()
        return

    try:
        logger.info(f"Starting ingestion process for: {doc.filename}")
        doc.status = "processing"
        db.commit()

        # 1. Render pages as images (using PyMuPDF rasterizer)
        page_images = pdf_service.render_pages(file_path)
        doc.page_count = len(page_images)
        db.commit()

        # 2. Extract layouts (PyMuPDF native structure + OCR fallback on scanned pages)
        chunks = pdf_service.extract_layout(file_path, page_images)
        
        # 3. Generate embeddings and index in FAISS and SQLite
        retriever.index_document_chunks(db, document_id, chunks)

        # 4. Finalize state
        doc.status = "ready"
        db.commit()
        logger.info(f"Ingestion pipeline completed successfully for document: {doc.filename}")
        
    except Exception as e:
        logger.error(f"Ingestion failed for {doc.filename}: {e}", exc_info=True)
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
    finally:
        db.close()

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Uploads a PDF or image, saves it, and schedules background layout indexing."""
    filename = file.filename
    if not filename.lower().endswith(".pdf") and not filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail="Only PDF and PNG/JPG images are supported.")

    # Save to local storage
    document_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1]
    saved_filename = f"{document_id}{ext}"
    saved_path = os.path.join(settings.uploads_dir, saved_filename)

    try:
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Saved uploaded file to: {saved_path}")
    except Exception as e:
        logger.error(f"Failed to write file to disk: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save upload: {e}")

    # Register document in metadata database
    db_doc = Document(
        id=document_id,
        filename=filename,
        status="pending"
    )
    db.add(db_doc)
    db.commit()

    # Schedule complete processing in a background worker
    # We pass the session creator local maker to ensure thread safety
    from models.db_models import SessionLocal
    background_tasks.add_task(
        process_document_pipeline,
        document_id,
        saved_path,
        SessionLocal
    )

    return UploadResponse(
        document_id=document_id,
        filename=filename,
        status="pending"
    )

@router.get("/status/{document_id}", response_model=DocumentSchema)
async def get_status(document_id: str, db: Session = Depends(get_db)):
    """Retrieves document parsing progress status."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
