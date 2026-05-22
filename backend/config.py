import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database Settings
    # Defaults to a local SQLite database file in the backend root
    database_url: str = "sqlite:///./research_rag.db"
    
    # Storage Paths
    storage_path: str = "./storage"
    uploads_dir: str = "./storage/uploads"
    pages_dir: str = "./storage/pages"
    figures_dir: str = "./storage/figures"
    vector_dir: str = "./storage/vector_indices"
    
    # LLM Settings (Google Gemini)
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.2
    gemini_max_tokens: int = 2048
    gemini_timeout_seconds: int = 120
    
    # Embedding Model Settings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16
    
    # Retrieval & RAG
    top_k_vector: int = 5
    min_evidence_relevance: float = 0.25
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # Ensure all directories exist
    for directory in [
        settings.storage_path,
        settings.uploads_dir,
        settings.pages_dir,
        settings.figures_dir,
        settings.vector_dir
    ]:
        os.makedirs(directory, exist_ok=True)
    return settings
