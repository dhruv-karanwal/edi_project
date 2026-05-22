import os
import faiss
import json
import numpy as np
from typing import List, Dict, Any, Tuple
from config import get_settings
from utils.logger import logger

settings = get_settings()

class FAISSIndex:
    """Encapsulates a local FAISS index for high-speed document semantic search."""
    
    def __init__(self, document_id: str, dimension: int = 384):
        self.document_id = document_id
        self.dimension = dimension
        self.index_path = os.path.join(settings.vector_dir, f"{document_id}.index")
        self.mapping_path = os.path.join(settings.vector_dir, f"{document_id}.json")
        
        # Initialize internal index
        # IndexFlatIP uses Inner Product (equivalent to Cosine Similarity when vectors are normalized)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.id_to_chunk_map: Dict[str, str] = {}  # maps index position (str) -> chunk_uuid

        self.load()

    def load(self):
        """Loads index and metadata mapping from disk if present."""
        if os.path.exists(self.index_path) and os.path.exists(self.mapping_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.mapping_path, "r", encoding="utf-8") as f:
                    self.id_to_chunk_map = json.load(f)
                logger.info(f"Loaded existing FAISS index for document: {self.document_id}")
            except Exception as e:
                logger.error(f"Failed to load FAISS index for {self.document_id}: {e}")
                # Reset to empty flat index
                self.index = faiss.IndexFlatIP(self.dimension)
                self.id_to_chunk_map = {}

    def save(self):
        """Persists index and metadata mapping to disk."""
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.mapping_path, "w", encoding="utf-8") as f:
                json.dump(self.id_to_chunk_map, f, indent=2)
            logger.info(f"Saved FAISS index to: {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")

    def add_vectors(self, embeddings: np.ndarray, chunk_ids: List[str]):
        """
        Adds vectors to the FAISS index.
        embeddings: np.ndarray of shape (num_chunks, dimension)
        chunk_ids: list of string UUIDs matching chunk_models in DB
        """
        if len(embeddings) != len(chunk_ids):
            raise ValueError("Size mismatch between embeddings and chunk IDs")
        
        if len(embeddings) == 0:
            return

        # Ensure type is float32 for FAISS operations
        embeddings = np.array(embeddings, dtype=np.float32)
        
        # L2-normalize vectors for cosine similarity equivalent using Inner Product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1.0
        normalized_embeddings = embeddings / norms
        
        start_idx = self.index.ntotal
        self.index.add(normalized_embeddings)
        
        # Store index mapping
        for offset, chunk_id in enumerate(chunk_ids):
            self.id_to_chunk_map[str(start_idx + offset)] = chunk_id
            
        self.save()

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Queries the FAISS index.
        query_embedding: np.ndarray of shape (dimension,) or (1, dimension)
        Returns a list of Tuple[chunk_uuid, similarity_score].
        """
        if self.index.ntotal == 0:
            return []

        # Prepare dimensions
        query_embedding = np.array(query_embedding, dtype=np.float32)
        if len(query_embedding.shape) == 1:
            query_embedding = np.expand_dims(query_embedding, axis=0)

        # L2 normalize search query vector
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        top_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_embedding, top_k)
        
        results = []
        # scores and indices are arrays of shape (1, top_k)
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk_uuid = self.id_to_chunk_map.get(str(idx))
            if chunk_uuid:
                results.append((chunk_uuid, float(score)))
                
        return results

    def delete(self):
        """Cleans up index files from storage."""
        try:
            if os.path.exists(self.index_path):
                os.remove(self.index_path)
            if os.path.exists(self.mapping_path):
                os.remove(self.mapping_path)
            logger.info(f"Deleted FAISS index files for: {self.document_id}")
        except Exception as e:
            logger.error(f"Error deleting index files: {e}")
