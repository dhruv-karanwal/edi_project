from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from db.database import init_db
from config import get_settings
from llm.ollama_client import OllamaClient
import uvicorn
from api.routers import ingest, query, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Initializing database...")
    init_db()
    print("✓ Database initialized")
    
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        print("Checking Ollama models...")
        try:
            llm_client = OllamaClient()
            llm_client.ensure_models_available()
            print("✓ Ollama models ready")
        except Exception as e:
            print(f"⚠ Warning: Ollama not ready: {e}")
            print("⚠ Backend will stay up; answer generation may fail until Ollama is available.")
    elif provider == "gemini":
        if settings.gemini_api_key:
            print("✓ Gemini provider configured")
        else:
            print("⚠ GEMINI_API_KEY is missing; answer generation will return a graceful error.")
    else:
        print(f"⚠ Unsupported LLM_PROVIDER: {provider}")
    
    yield
    # Shutdown
    print("Shutting down...")

app = FastAPI(
    title="Research RAG API",
    description="Diagram & Chart Understanding RAG for Research Papers (FREE Stack)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(documents.router)

@app.get("/api/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "version": "1.0.0",
        "stack": f"free ({settings.llm_provider} + bge-m3)"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)