from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from db.database import get_db
from db.models import Document
from file_storage.file_store import FileStore
from ingestion.pipeline import IngestionPipeline
from api.models.response_models import UploadResponse, DocumentResponse

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])

file_store = FileStore()

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a PDF and start processing."""
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Create document record
    document = Document(
        filename=file.filename,
        file_path="",
        status="pending"
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Save PDF file
    try:
        file_path = file_store.save_pdf(str(document.id), file.file, file.filename)
        document.file_path = file_path
        db.commit()
    except Exception as e:
        db.delete(document)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Start background processing
    background_tasks.add_task(process_document_task, str(document.id))
    
    return UploadResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status
    )

def process_document_task(document_id: str):
    """Background task to process document."""
    from db.database import SessionLocal
    db = SessionLocal()
    try:
        pipeline = IngestionPipeline(db)
        pipeline.process_document(document_id)
    finally:
        db.close()

@router.get("/status/{document_id}", response_model=DocumentResponse)
async def get_status(document_id: UUID, db: Session = Depends(get_db)):
    """Get processing status of a document."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse.from_orm(document)