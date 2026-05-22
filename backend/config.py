import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    # Defaults to a local SQLite database file in the backend root
    database_url: str = "sqlite:///./research_rag.db"

    # ── Storage Paths ─────────────────────────────────────────────────────────
    storage_path: str = "./storage"
    uploads_dir: str = "./storage/uploads"
    pages_dir: str = "./storage/pages"
    figures_dir: str = "./storage/figures"
    vector_dir: str = "./storage/vector_indices"

    # ── LLM Settings (Google Gemini) ──────────────────────────────────────────
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.2
    gemini_max_tokens: int = 2048
    gemini_timeout_seconds: int = 120

    # ── Embedding Model (SentenceTransformers) ────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16

    # ── Retrieval & RAG ───────────────────────────────────────────────────────
    top_k_vector: int = 5
    min_evidence_relevance: float = 0.25

    # ══════════════════════════════════════════════════════════════════════════
    # NEW — v2.0 Advanced AI Features
    # ══════════════════════════════════════════════════════════════════════════

    # ── Feature 1: OpenCV OCR Preprocessing ──────────────────────────────────
    # Toggle to enable/disable the OpenCV image enhancement pipeline before OCR
    enable_ocr_preprocessing: bool = True
    # Prioritise EasyOCR over Tesseract (useful for Render/cloud deployments without Tesseract binary)
    prefer_easyocr: bool = True

    # ── Feature 2: AI Layout Detection (surya-ocr) ────────────────────────────
    # Toggle AI-powered layout region detection.
    # When False, falls back to existing PyMuPDF heuristic extraction.
    enable_layout_detection: bool = True

    # ── Feature 3: CLIP Image Embeddings ─────────────────────────────────────
    # Enable CLIP visual embeddings for figure/table semantic image retrieval
    enable_clip: bool = True
    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "openai"
    # Dimension of CLIP image/text embeddings (ViT-B-32 = 512)
    clip_embedding_dim: int = 512

    # ── Feature 4: Hybrid Retrieval ───────────────────────────────────────────
    # Enable hybrid BM25 + FAISS + CLIP retrieval pipeline.
    # When False, uses legacy FAISS-only semantic retrieval.
    enable_hybrid_retrieval: bool = True
    # Retrieval stage weights (must sum to 1.0 for intuitive scoring)
    bm25_weight: float = 0.30    # Keyword (BM25) contribution
    faiss_weight: float = 0.50   # Semantic (FAISS) contribution
    clip_weight: float = 0.20    # Visual (CLIP) contribution

    # ── Feature 5: LayoutLMv3 Multimodal Understanding ───────────────────────
    # DISABLED by default — model is ~900MB and slow on CPU (30-60s/page).
    # Enable only for GPU environments or single-page analysis.
    enable_layoutlm: bool = False
    layoutlm_model: str = "microsoft/layoutlmv3-base"
    # Dimension of LayoutLMv3 CLS token embeddings
    layoutlm_embedding_dim: int = 768

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # Ensure all storage directories exist at startup
    for directory in [
        settings.storage_path,
        settings.uploads_dir,
        settings.pages_dir,
        settings.figures_dir,
        settings.vector_dir,
    ]:
        os.makedirs(directory, exist_ok=True)
    return settings
