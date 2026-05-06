from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    database_url: str
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2:3b"
    ollama_vlm_model: str = "llava:13b"

    # LLM Provider
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_timeout_seconds: int = 120
    
    # Storage
    storage_path: str = "./storage"
    
    # Embedding
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    
    # LLM
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    
    # Retrieval
    top_k_vector: int = 10
    top_k_graph: int = 5
    rerank_top_k: int = 8
    max_evidence_per_answer: int = 8
    min_evidence_relevance: float = 0.35
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()