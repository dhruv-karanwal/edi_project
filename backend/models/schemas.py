from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

class DocumentSchema(BaseModel):
    id: str
    filename: str
    status: str
    page_count: Optional[int] = None
    created_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class ChunkSchema(BaseModel):
    id: str
    chunk_type: str
    content: str
    page_number: int
    section_title: Optional[str] = None
    caption: Optional[str] = None
    image_path: Optional[str] = None
    bbox: Optional[BoundingBox] = None

    class Config:
        from_attributes = True

class Evidence(BaseModel):
    chunk_id: str
    chunk_type: str
    page_number: int
    section_title: Optional[str] = None
    snippet: str
    image_url: Optional[str] = None
    relevance_score: float

class QueryRequest(BaseModel):
    document_id: str
    question: str
    conversation_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    conversation_id: str
    evidence: List[Evidence]

class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str

class MessageSchema(BaseModel):
    role: str
    content: str
    evidence: Optional[List[Evidence]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ConversationSchema(BaseModel):
    conversation_id: Optional[str] = None
    document_id: str
    messages: List[MessageSchema]

class ConversationSummary(BaseModel):
    conversation_id: str
    created_at: datetime
    message_count: int
    last_message_at: Optional[datetime] = None

class DocumentConversationsResponse(BaseModel):
    document_id: str
    conversations: List[ConversationSummary]
