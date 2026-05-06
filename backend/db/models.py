from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from .database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    status = Column(String(50), default="pending")  # pending|processing|ready|failed
    page_count = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    error_message = Column(Text)
    
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_type = Column(String(50), nullable=False)  # text|figure|table|equation|caption
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    section_title = Column(String(500))
    caption = Column(Text)
    image_path = Column(Text)
    bbox = Column(JSON)  # {x0, y0, x1, y1}
    extra_metadata = Column("metadata", JSON)
    chunk_index = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    document = relationship("Document", back_populates="chunks")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    document = relationship("Document", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user|assistant
    content = Column(Text, nullable=False)
    evidence = Column(JSON)  # list of evidence references
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="messages")