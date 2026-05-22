import os
import sys
from contextlib import asynccontextmanager

# Add parent/current directory to path to ensure standard module resolution
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from models.db_models import init_db
from api import documents, ingest, query
from utils.logger import logger

# Initialize settings and ensure storage folders exist
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise the relational tables on startup
    logger.info("Starting up FastAPI application...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}", exc_info=True)
    yield
    logger.info("Shutting down FastAPI application...")

app = FastAPI(
    title="Neural Machine Reading with Visual Grounding Backend",
    description="FastAPI Multimodal Document Understanding Engine powered by Gemini & layout-aware OCR",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local dev access (or specify http://localhost:3000)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(ingest.router)
app.include_router(documents.router)
app.include_router(query.router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Multimodal Document Intelligence API Engine",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting development server via uvicorn...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
