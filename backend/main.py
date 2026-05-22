import os
import sys
from contextlib import asynccontextmanager

# Add parent/current directory to path to ensure standard module resolution
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from models.db_models import init_db
from api import documents, ingest, query
from utils.logger import logger

# Initialize settings and ensure storage folders exist at import time
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown lifecycle events.
    """
    logger.info("==================================================")
    logger.info("  Neural Machine Reading System Backend Starting  ")
    logger.info("==================================================")
    logger.info(f"Target Database URL: {settings.database_url}")
    logger.info(f"Storage Directory Path: {settings.storage_path}")
    logger.info(f"Gemini LLM Model Configured: {settings.gemini_model}")
    logger.info(f"OpenCV OCR Preprocessing: {settings.enable_ocr_preprocessing}")
    logger.info(f"surya AI Layout Detection: {settings.enable_layout_detection}")
    logger.info(f"CLIP Image Embeddings: {settings.enable_clip}")
    logger.info(f"Hybrid Retrieval Active: {settings.enable_hybrid_retrieval}")
    logger.info(f"LayoutLMv3 (Opt-in Heavy Model): {settings.enable_layoutlm}")
    logger.info("--------------------------------------------------")

    # ── Auto-create all critical storage sub-directories ───────────────────
    for dir_path in [
        settings.storage_path,
        settings.uploads_dir,
        settings.pages_dir,
        settings.figures_dir,
        settings.vector_dir
    ]:
        try:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"Auto-created storage directory: {dir_path}")
        except Exception as dir_err:
            logger.error(f"Failed to create directory {dir_path}: {dir_err}")

    # ── Initialise SQLite relational tables ─────────────────────────────────
    try:
        init_db()
        logger.info("SQLite relational database successfully initialized.")
    except Exception as db_err:
        logger.error(f"Error during SQLite database initialization: {db_err}", exc_info=True)

    yield

    logger.info("==================================================")
    logger.info("  Neural Machine Reading System Backend Shutting Down  ")
    logger.info("==================================================")


app = FastAPI(
    title="Neural Machine Reading with Visual Grounding Backend",
    description="FastAPI Multimodal Document Understanding Engine powered by Gemini & layout-aware OCR",
    version="1.0.0",
    lifespan=lifespan
)

# ── CORS Middleware Configuration ──────────────────────────────────────────
# Allow both absolute local development access and production deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mounting Module Routes ────────────────────────────────────────────────
app.include_router(ingest.router)
app.include_router(documents.router)
app.include_router(query.router)

# ── Health and Base Info Routes ───────────────────────────────────────────

@app.get("/", tags=["system"])
async def root():
    """
    Root API health and description status check.
    """
    return {
        "status": "online",
        "service": "Advanced Neural Machine Reading Backend Engine",
        "version": "2.0.0",
        "documentation": "/docs",
        "deployment_platform": "Render.com compatible"
    }


@app.get("/health", tags=["system"])
async def health_check():
    """
    System check to verify storage write permissions, database access,
    and current AI model states. Helpful for Render build diagnostics.
    """
    health_status = {
        "status": "healthy",
        "database": "connected",
        "storage": {
            "path": settings.storage_path,
            "writable": False
        },
        "features": {
            "opencv_preprocessing": settings.enable_ocr_preprocessing,
            "easyocr_priority": settings.prefer_easyocr,
            "surya_layout": settings.enable_layout_detection,
            "clip_vision": settings.enable_clip,
            "hybrid_retrieval": settings.enable_hybrid_retrieval,
            "layoutlmv3": settings.enable_layoutlm
        }
    }

    # Verify storage writable
    test_file_path = os.path.join(settings.storage_path, ".health_check_write_test")
    try:
        with open(test_file_path, "w") as f:
            f.write("OK")
        os.remove(test_file_path)
        health_status["storage"]["writable"] = True
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["storage"]["writable"] = False
        health_status["storage"]["error"] = str(e)
        logger.error(f"Health check storage write test failed: {e}")

    # Database connectivity test
    try:
        from models.db_models import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        # Simple database ping
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as db_err:
        health_status["status"] = "degraded"
        health_status["database"] = f"disconnected: {db_err}"
        logger.error(f"Health check database connection failed: {db_err}")

    # Determine status response code
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=health_status)


# ── Global Exception Handlers ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all error handler to prevent FastAPI from returning 500 HTML pages
    and maintain clean JSON errors for the frontend client.
    """
    logger.error(f"Unhandled Exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred while processing your request.",
            "error_type": type(exc).__name__,
            "message": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    # Read port from environment for seamless Render/Docker containerisation
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting production-ready server via Uvicorn on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
