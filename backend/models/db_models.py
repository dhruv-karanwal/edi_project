import uuid
import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    DateTime, ForeignKey, Text, JSON, event, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import get_settings
from utils.logger import logger

settings = get_settings()

# ── Database Engine ───────────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# Enable SQLite foreign key enforcement
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM Models ────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename      = Column(String(255), nullable=False)
    status        = Column(String(50), default="pending")   # pending/processing/ready/failed
    page_count    = Column(Integer, nullable=True)
    created_at    = Column(DateTime, default=datetime.datetime.utcnow)
    error_message = Column(Text, nullable=True)

    chunks        = relationship("Chunk",        back_populates="document", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id     = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_type      = Column(String(50), nullable=False)   # text/figure/table/caption/equation
    content         = Column(Text, nullable=False)
    page_number     = Column(Integer, nullable=False)
    section_title   = Column(String(500), nullable=True)
    caption         = Column(Text, nullable=True)
    image_path      = Column(Text, nullable=True)
    bbox            = Column(JSON, nullable=True)           # normalized 0-1000 bounding box

    # ── v2.0 NEW COLUMNS: AI Layout Detection metadata ────────────────────────
    # Populated by surya LayoutEngine when ENABLE_LAYOUT_DETECTION=true
    layout_label      = Column(String(100), nullable=True)   # e.g. "Title", "Figure", "Table"
    layout_confidence = Column(Float,       nullable=True)   # detection confidence [0, 1]

    # Populated by the hybrid retriever to show which pipeline found this chunk
    retrieval_source  = Column(String(50),  nullable=True)   # "bm25"|"semantic"|"visual"|"multimodal"

    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    created_at  = Column(DateTime, default=datetime.datetime.utcnow)

    document = relationship("Document", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role            = Column(String(20), nullable=False)    # "user" | "assistant"
    content         = Column(Text, nullable=False)
    evidence        = Column(JSON, nullable=True)           # List[Evidence] serialized
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


# ── Database Initialization ────────────────────────────────────────────────────

def _run_migrations(conn):
    """
    Lightweight migration: add new v2.0 columns to existing 'chunks' table
    without requiring Alembic. SQLite's ALTER TABLE ADD COLUMN is used.

    Safe to run on both fresh installs (columns don't exist yet) and
    already-upgraded databases (gracefully skips existing columns).
    """
    # Inspect existing columns
    result   = conn.execute(text("PRAGMA table_info(chunks)"))
    existing = {row[1] for row in result.fetchall()}   # row[1] = column name

    new_columns = [
        ("layout_label",      "VARCHAR(100)"),
        ("layout_confidence", "FLOAT"),
        ("retrieval_source",  "VARCHAR(50)"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing:
            logger.info(f"Running migration: adding column '{col_name}' to chunks table.")
            conn.execute(text(f"ALTER TABLE chunks ADD COLUMN {col_name} {col_type}"))


def init_db():
    """
    Create all tables and run lightweight column-level migrations.
    Called once at application startup via the FastAPI lifespan hook.
    """
    logger.info("Initializing relational database...")
    Base.metadata.create_all(bind=engine)

    # Run migrations to add v2.0 columns to existing installations
    with engine.begin() as conn:
        _run_migrations(conn)

    logger.info("Database tables initialized and migrations applied successfully.")


def get_db():
    """FastAPI dependency — yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
