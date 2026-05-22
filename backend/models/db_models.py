import uuid
import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, ForeignKey, Text, JSON, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import get_settings
from utils.logger import logger

settings = get_settings()

# Setup database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# Enable foreign keys for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")  # 'pending', 'processing', 'ready', 'failed'
    page_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    error_message = Column(Text, nullable=True)
    
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_type = Column(String(50), nullable=False)  # 'text', 'figure', 'table', 'equation', 'caption'
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    section_title = Column(String(500), nullable=True)
    caption = Column(Text, nullable=True)
    image_path = Column(Text, nullable=True)
    bbox = Column(JSON, nullable=True)  # dict/list mapping coordinate bounding box
    
    document = relationship("Document", back_populates="chunks")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    document = relationship("Document", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant'
    content = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=True)  # List of dicts representing source citations
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")

def init_db():
    """Initializes tables in database."""
    logger.info("Initializing relational database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully")

def get_db():
    """FastAPI db session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
