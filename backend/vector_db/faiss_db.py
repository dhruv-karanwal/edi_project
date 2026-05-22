"""
Vector Database — FAISS Index Wrapper

Encapsulates a local FAISS IndexFlatIP (Inner Product) index for high-speed
document semantic search.

v2.0 Enhancement:
  - Supports arbitrary embedding dimensions (384 for SentenceTransformers,
    512 for CLIP, 768 for LayoutLMv3) via the `dimension` constructor param.
  - Accepts an optional `suffix` to namespace index files, allowing multiple
    parallel indexes per document:
        {doc_id}.index         → text (SentenceTransformers, dim=384)
        {doc_id}_clip.index    → visual (CLIP, dim=512)
        {doc_id}_layoutlm.index → multimodal (LayoutLMv3, dim=768)
"""

import os
import faiss
import json
import numpy as np
from typing import List, Dict, Tuple
from config import get_settings
from utils.logger import logger

settings = get_settings()


class FAISSIndex:
    """
    Persistent FAISS index for a single document and embedding space.

    Uses IndexFlatIP (Inner Product) — equivalent to cosine similarity
    when all stored vectors are L2-normalized prior to insertion.

    Files on disk:
        {vector_dir}/{document_id}{suffix}.index   — binary FAISS index
        {vector_dir}/{document_id}{suffix}.json    — position → chunk_UUID map
    """

    def __init__(self, document_id: str, dimension: int = 384, suffix: str = ""):
        """
        Args:
            document_id: UUID of the parent document.
            dimension:   Embedding dimension (384=text, 512=CLIP, 768=LayoutLM).
            suffix:      File suffix to namespace this index (e.g. "_clip").
        """
        self.document_id = document_id
        self.dimension   = dimension
        self.suffix      = suffix

        # Derive storage paths
        base = os.path.join(settings.vector_dir, f"{document_id}{suffix}")
        self.index_path   = f"{base}.index"
        self.mapping_path = f"{base}.json"

        # Initialize empty Inner Product index
        self.index = faiss.IndexFlatIP(self.dimension)

        # Maps string position index → chunk UUID string
        self.id_to_chunk_map: Dict[str, str] = {}

        # Attempt to restore from disk
        self.load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self):
        """Load index and mapping from disk if both files exist."""
        if os.path.exists(self.index_path) and os.path.exists(self.mapping_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.mapping_path, "r", encoding="utf-8") as f:
                    self.id_to_chunk_map = json.load(f)
                logger.info(
                    f"Loaded FAISS index '{self.document_id}{self.suffix}' "
                    f"({self.index.ntotal} vectors, dim={self.dimension})."
                )
            except Exception as e:
                logger.error(
                    f"Failed to load FAISS index for '{self.document_id}{self.suffix}': {e}"
                )
                # Reset to empty state on corruption
                self.index = faiss.IndexFlatIP(self.dimension)
                self.id_to_chunk_map = {}

    def save(self):
        """Persist the index and UUID mapping to disk."""
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.mapping_path, "w", encoding="utf-8") as f:
                json.dump(self.id_to_chunk_map, f, indent=2)
            logger.info(f"Saved FAISS index to: {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to save FAISS index '{self.document_id}{self.suffix}': {e}")

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_vectors(self, embeddings: np.ndarray, chunk_ids: List[str]):
        """
        Add embedding vectors to the FAISS index.

        Vectors are L2-normalized before insertion so that IndexFlatIP
        computes cosine similarity (dot product of unit vectors).

        Args:
            embeddings: np.ndarray of shape (N, dimension) in float32.
            chunk_ids:  List of N chunk UUID strings.
        """
        if len(embeddings) != len(chunk_ids):
            raise ValueError(
                f"Size mismatch: {len(embeddings)} embeddings vs {len(chunk_ids)} chunk IDs"
            )
        if len(embeddings) == 0:
            return

        embeddings = np.array(embeddings, dtype=np.float32)

        # L2-normalize each row (avoids division by zero for zero vectors)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = embeddings / norms

        start_idx = self.index.ntotal
        self.index.add(normalized)

        # Record position → UUID mapping
        for offset, chunk_id in enumerate(chunk_ids):
            self.id_to_chunk_map[str(start_idx + offset)] = chunk_id

        self.save()
        logger.info(
            f"Added {len(chunk_ids)} vectors to FAISS '{self.document_id}{self.suffix}' "
            f"(total: {self.index.ntotal})."
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Query the FAISS index for the most similar chunk UUIDs.

        Args:
            query_embedding: np.ndarray of shape (dimension,).
            top_k:           Maximum number of results to return.

        Returns:
            List of (chunk_uuid, cosine_similarity_score) tuples,
            sorted by descending score.
        """
        if self.index.ntotal == 0:
            return []

        query = np.array(query_embedding, dtype=np.float32)
        if query.ndim == 1:
            query = np.expand_dims(query, axis=0)  # shape: (1, dim)

        # L2 normalize the query vector
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        actual_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query, actual_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk_uuid = self.id_to_chunk_map.get(str(idx))
            if chunk_uuid:
                results.append((chunk_uuid, float(score)))

        return results  # already sorted by FAISS (descending score)

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self):
        """Remove index files from disk."""
        try:
            if os.path.exists(self.index_path):
                os.remove(self.index_path)
            if os.path.exists(self.mapping_path):
                os.remove(self.mapping_path)
            logger.info(f"Deleted FAISS index files for '{self.document_id}{self.suffix}'.")
        except Exception as e:
            logger.error(f"Error deleting FAISS index '{self.document_id}{self.suffix}': {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def vector_count(self) -> int:
        """Number of vectors currently stored in the index."""
        return self.index.ntotal

    def exists(self) -> bool:
        """True if index files already exist on disk."""
        return os.path.exists(self.index_path) and os.path.exists(self.mapping_path)
