from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Session:
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables."""
    from .models import Document, Chunk, Conversation, Message
    Base.metadata.create_all(bind=engine)

    # Backfill/repair legacy chunk schemas created before the model/schema aligned.
    with engine.begin() as connection:
        inspector = inspect(connection)
        if inspector.has_table("chunks"):
            columns = {column["name"] for column in inspector.get_columns("chunks")}
            if "metadata" not in columns and "extra_metadata" in columns:
                connection.execute(text("ALTER TABLE chunks RENAME COLUMN extra_metadata TO metadata"))