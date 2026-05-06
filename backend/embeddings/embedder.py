from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
from config import get_settings
import torch

settings = get_settings()

class Embedder:
    """Handle text embeddings using bge-m3."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        print(f"Loading embedding model: {settings.embedding_model}")
        self.model = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device
        )
        self.dimension = self.model.get_sentence_embedding_dimension()
        self._initialized = True
        print(f"✓ Embedding model loaded (dimension: {self.dimension})")
    
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str], batch_size: int = None) -> List[List[float]]:
        """Embed a batch of texts."""
        if batch_size is None:
            batch_size = settings.embedding_batch_size
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=True
        )
        return embeddings.tolist()
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.dimension