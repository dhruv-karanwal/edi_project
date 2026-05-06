from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class UploadResponse(BaseModel):
    document_id: UUID
    filename: str
    status: str

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    page_count: Optional[int]
    created_at: datetime
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class ChunkResponse(BaseModel):
    id: UUID
    chunk_type: str
    content: str
    page_number: int
    section_title: Optional[str]
    caption: Optional[str]
    image_path: Optional[str]
    bbox: Optional[Dict[str, float]]
    
    class Config:
        from_attributes = True

class Evidence(BaseModel):
    chunk_id: UUID
    chunk_type: str
    page_number: int
    section_title: Optional[str]
    snippet: str
    image_url: Optional[str]
    relevance_score: float

class QueryResponse(BaseModel):
    answer: str
    conversation_id: UUID
    evidence: List[Evidence]