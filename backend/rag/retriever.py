"""
Feature 4: Hybrid Retrieval Engine (BM25 + FAISS + CLIP)

Upgrades the legacy single-stage FAISS semantic retrieval into a
multi-stage pipeline that combines three complementary search methods:

  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 1: BM25 Keyword Search                                   │
  │    • TF-IDF based keyword matching via rank-bm25                │
  │    • Best for: exact term matches, acronyms, proper nouns       │
  ├─────────────────────────────────────────────────────────────────┤
  │  Stage 2: FAISS Semantic Search                                 │
  │    • Dense vector cosine similarity via SentenceTransformers    │
  │    • Best for: paraphrased queries, conceptual similarity       │
  ├─────────────────────────────────────────────────────────────────┤
  │  Stage 3: CLIP Visual Search                                    │
  │    • Cross-modal text→image retrieval via CLIP embeddings       │
  │    • Best for: queries about figures, charts, diagrams, tables  │
  └─────────────────────────────────────────────────────────────────┘
                         │
              Weighted Score Fusion
       score = w_bm25*s1 + w_faiss*s2 + w_clip*s3
                         │
              Deduplication by chunk_id
                         │
              Sort by final score DESC
                         │
              Return top-k evidence with source labels

Score Normalization:
  BM25 scores are normalized to [0, 1] by dividing by the max score.
  FAISS and CLIP scores are already cosine similarities in [0, 1].

Backward Compatibility:
  - Documents indexed before v2.0 (no BM25/CLIP files) still work;
    missing stages are automatically skipped.
  - When ENABLE_HYBRID_RETRIEVAL=false, only FAISS is used (v1 behavior).
"""

import os
import pickle
import re
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from config import get_settings
from utils.logger import logger
from models.db_models import Chunk
from vector_db.faiss_db import FAISSIndex

settings = get_settings()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\b\w+\b", text.lower())


def _normalize_scores(score_dict: Dict[str, float]) -> Dict[str, float]:
    """
    Min-max normalize a dict of {id: score} to [0, 1].
    Returns original dict unchanged if all scores are 0 or it's empty.
    """
    if not score_dict:
        return {}
    max_score = max(score_dict.values())
    min_score = min(score_dict.values())
    spread = max_score - min_score
    if spread == 0:
        return {k: 1.0 for k in score_dict}
    return {k: (v - min_score) / spread for k, v in score_dict.items()}


# ─── BM25 Persistence ─────────────────────────────────────────────────────────

def _bm25_path(document_id: str) -> str:
    return os.path.join(settings.vector_dir, f"{document_id}_bm25.pkl")


def _save_bm25(document_id: str, bm25_obj, chunk_ids: List[str]):
    """Serialize BM25 index and chunk ID list to disk via pickle."""
    try:
        with open(_bm25_path(document_id), "wb") as f:
            pickle.dump({"bm25": bm25_obj, "chunk_ids": chunk_ids}, f)
        logger.info(f"BM25 index saved for document: {document_id}")
    except Exception as e:
        logger.error(f"Failed to save BM25 index: {e}")


def _load_bm25(document_id: str):
    """
    Load BM25 index from disk.
    Returns (bm25_obj, chunk_ids) or (None, []) if unavailable.
    """
    path = _bm25_path(document_id)
    if not os.path.exists(path):
        return None, []
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        return data["bm25"], data["chunk_ids"]
    except Exception as e:
        logger.error(f"Failed to load BM25 index: {e}")
        return None, []


# ─── Retriever ────────────────────────────────────────────────────────────────

class Retriever:
    """
    Multi-stage document retrieval engine.

    Manages:
      - SentenceTransformer text embeddings + FAISS index (text/semantic)
      - rank-bm25 keyword index (text/keyword)
      - CLIP visual embeddings + FAISS index (figure/visual)
      - LayoutLMv3 embeddings + FAISS index (multimodal, optional)

    Exposes:
      - index_document_chunks()  — called during ingestion
      - retrieve_context()       — called for each query
    """

    def __init__(self):
        self._embedder   = None     # SentenceTransformer (text)
        self._clip       = None     # CLIPEngine (visual)
        self.dimension   = 384      # SentenceTransformer default

    # ── Lazy Loaders ──────────────────────────────────────────────────────────

    def _get_embedder(self) -> SentenceTransformer:
        """Lazy-load SentenceTransformer text embedding model."""
        if self._embedder is None:
            logger.info(
                f"Loading SentenceTransformer: {settings.embedding_model} "
                f"on device: {settings.embedding_device}..."
            )
            self._embedder = SentenceTransformer(
                settings.embedding_model,
                device=settings.embedding_device
            )
            self.dimension = self._embedder.get_sentence_embedding_dimension()
            logger.info(f"SentenceTransformer loaded (dim={self.dimension}).")
        return self._embedder

    def _get_clip(self):
        """Lazy-load CLIPEngine (only when CLIP is enabled)."""
        if not settings.enable_clip:
            return None
        if self._clip is None:
            from vision.clip_engine import CLIPEngine
            self._clip = CLIPEngine()
        return self._clip

    # ── Indexing ──────────────────────────────────────────────────────────────

    def index_document_chunks(
        self,
        db: Session,
        document_id: str,
        raw_chunks: List[Dict[str, Any]]
    ):
        """
        Full indexing pipeline for a newly ingested document.

        Steps:
          1. Augment chunk texts with metadata for better embeddings
          2. Generate SentenceTransformer embeddings → FAISS (text)
          3. Build BM25 keyword index → pickle on disk
          4. Generate CLIP embeddings for figure/table chunks → FAISS (visual)
          5. (Optional) Generate LayoutLMv3 embeddings → FAISS (multimodal)
          6. Persist all Chunk records to SQLite
        """
        if not raw_chunks:
            logger.warning(f"No chunks to index for document: {document_id}")
            return

        embedder = self._get_embedder()

        # ── Step 1: Augment texts for richer embeddings ────────────────────────
        texts_to_embed = []
        for chunk in raw_chunks:
            text = chunk["content"]
            if chunk.get("section_title"):
                text = f"Section: {chunk['section_title']}\n{text}"
            if chunk.get("caption"):
                text = f"Caption: {chunk['caption']}\n{text}"
            texts_to_embed.append(text)

        # ── Step 2: Text Embeddings → FAISS ───────────────────────────────────
        logger.info(f"Generating text embeddings for {len(texts_to_embed)} chunks...")
        text_embeddings = embedder.encode(
            texts_to_embed,
            batch_size=settings.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        # ── Step 3: Persist Chunks to SQLite ──────────────────────────────────
        db_chunks = []
        for rc in raw_chunks:
            db_chunk = Chunk(
                document_id     = document_id,
                chunk_type      = rc["chunk_type"],
                content         = rc["content"],
                page_number     = rc["page_number"],
                section_title   = rc.get("section_title"),
                caption         = rc.get("caption"),
                image_path      = rc.get("image_path"),
                bbox            = rc.get("bbox"),
                # v2.0 layout fields
                layout_label      = rc.get("layout_label"),
                layout_confidence = rc.get("layout_confidence"),
            )
            db.add(db_chunk)
            db_chunks.append(db_chunk)

        db.commit()
        chunk_uuids = [c.id for c in db_chunks]
        logger.info(f"Saved {len(chunk_uuids)} chunks to SQLite.")

        # Index text embeddings into FAISS (default suffix = "")
        faiss_text = FAISSIndex(document_id, dimension=self.dimension)
        faiss_text.add_vectors(text_embeddings, chunk_uuids)

        # ── Step 4: BM25 Keyword Index ────────────────────────────────────────
        if settings.enable_hybrid_retrieval:
            self._build_bm25_index(document_id, raw_chunks, chunk_uuids)

        # ── Step 5: CLIP Visual Embeddings → FAISS ────────────────────────────
        if settings.enable_clip and settings.enable_hybrid_retrieval:
            self._build_clip_index(document_id, raw_chunks, chunk_uuids, db_chunks)

        # ── Step 6: LayoutLMv3 Multimodal Embeddings (optional) ───────────────
        if settings.enable_layoutlm:
            self._build_layoutlm_index(document_id, raw_chunks, chunk_uuids)

        logger.info(
            f"Indexing complete for document {document_id}: "
            f"{len(chunk_uuids)} chunks across all enabled indexes."
        )

    def _build_bm25_index(
        self,
        document_id: str,
        raw_chunks: List[Dict[str, Any]],
        chunk_uuids: List[str]
    ):
        """Build and persist a BM25Okapi index from chunk texts."""
        try:
            from rank_bm25 import BM25Okapi
            tokenized_corpus = [_tokenize(c["content"]) for c in raw_chunks]
            bm25 = BM25Okapi(tokenized_corpus)
            _save_bm25(document_id, bm25, chunk_uuids)
            logger.info(f"BM25 index built: {len(chunk_uuids)} documents.")
        except ImportError:
            logger.warning("rank-bm25 not installed. BM25 retrieval skipped.")
        except Exception as e:
            logger.error(f"BM25 indexing failed: {e}")

    def _build_clip_index(
        self,
        document_id: str,
        raw_chunks: List[Dict[str, Any]],
        chunk_uuids: List[str],
        db_chunks: List[Chunk]
    ):
        """
        Generate CLIP image embeddings for figure and table chunks.
        Only chunks with a saved image path and bounding box are embedded.
        """
        clip = self._get_clip()
        if clip is None:
            return

        from services.pdf_service import PDFService
        pdf_service = PDFService()

        clip_embeddings = []
        clip_ids        = []

        for idx, (chunk, db_chunk) in enumerate(zip(raw_chunks, db_chunks)):
            if chunk["chunk_type"] not in ("figure", "table"):
                continue

            bbox       = chunk.get("bbox")
            image_path = chunk.get("image_path")
            if not bbox or not image_path or not os.path.exists(image_path):
                continue

            # Derive on-disk crop path
            crop_filename = f"{document_id}_{db_chunk.id}.png"
            crop_path     = os.path.join(settings.figures_dir, crop_filename)

            # Crop the figure region if the file doesn't already exist
            if not os.path.exists(crop_path):
                pdf_service.crop_region(image_path, bbox, crop_path)

            if not os.path.exists(crop_path):
                continue

            # Generate CLIP embedding
            embedding = clip.encode_image(crop_path)
            if embedding is not None:
                clip_embeddings.append(embedding)
                clip_ids.append(db_chunk.id)

        if clip_embeddings:
            clip_faiss = FAISSIndex(
                document_id,
                dimension=settings.clip_embedding_dim,
                suffix="_clip"
            )
            clip_faiss.add_vectors(np.array(clip_embeddings), clip_ids)
            logger.info(f"CLIP index built: {len(clip_ids)} figure/table embeddings.")
        else:
            logger.info("No figure/table chunks with images found for CLIP indexing.")

    def _build_layoutlm_index(
        self,
        document_id: str,
        raw_chunks: List[Dict[str, Any]],
        chunk_uuids: List[str]
    ):
        """Generate LayoutLMv3 multimodal embeddings (optional, slow on CPU)."""
        try:
            from multimodal.layoutlm_engine import LayoutLMEngine
            engine = LayoutLMEngine()
            if not engine._load_model():
                return

            lm_embeddings = []
            lm_ids        = []

            for chunk, chunk_id in zip(raw_chunks, chunk_uuids):
                page_image = chunk.get("image_path", "")
                emb = engine.generate_embedding(chunk, page_image)
                if emb is not None:
                    lm_embeddings.append(emb)
                    lm_ids.append(chunk_id)

            if lm_embeddings:
                lm_faiss = FAISSIndex(
                    document_id,
                    dimension=settings.layoutlm_embedding_dim,
                    suffix="_layoutlm"
                )
                lm_faiss.add_vectors(np.array(lm_embeddings), lm_ids)
                logger.info(f"LayoutLMv3 index built: {len(lm_ids)} chunk embeddings.")

        except Exception as e:
            logger.error(f"LayoutLMv3 indexing failed (non-critical): {e}")

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve_context(
        self,
        db: Session,
        document_id: str,
        query: str,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Run the hybrid retrieval pipeline for a user query.

        Returns a unified, deduplicated, score-fused list of evidence dicts
        sorted by descending relevance score.

        When ENABLE_HYBRID_RETRIEVAL=false, falls back to FAISS-only search
        (preserves v1.0 behavior exactly).
        """
        if top_k is None:
            top_k = settings.top_k_vector

        if not settings.enable_hybrid_retrieval:
            # ── Legacy mode: FAISS-only ────────────────────────────────────
            return self._faiss_only_retrieve(db, document_id, query, top_k)

        # ── Hybrid mode: BM25 + FAISS + CLIP ──────────────────────────────
        logger.info(
            f"[Hybrid Retrieval] Query='{query[:60]}...' "
            f"(BM25 w={settings.bm25_weight}, "
            f"FAISS w={settings.faiss_weight}, "
            f"CLIP w={settings.clip_weight})"
        )

        embedder       = self._get_embedder()
        query_vector   = embedder.encode(query, convert_to_numpy=True)

        # Fetch more candidates per stage to ensure diverse results after fusion
        stage_k = max(top_k * 3, 15)

        # ── Stage 1: BM25 Keyword Search ──────────────────────────────────
        bm25_scores: Dict[str, float] = {}
        bm25_obj, bm25_ids = _load_bm25(document_id)
        if bm25_obj is not None:
            try:
                query_tokens  = _tokenize(query)
                raw_scores    = bm25_obj.get_scores(query_tokens)
                # Map scores back to chunk UUIDs
                for idx, score in enumerate(raw_scores):
                    if idx < len(bm25_ids) and score > 0:
                        bm25_scores[bm25_ids[idx]] = float(score)
                bm25_scores = _normalize_scores(bm25_scores)
                logger.info(f"  [BM25]  {len(bm25_scores)} non-zero matches.")
            except Exception as e:
                logger.warning(f"BM25 retrieval failed (skipping): {e}")

        # ── Stage 2: FAISS Semantic Search ────────────────────────────────
        faiss_scores: Dict[str, float] = {}
        try:
            text_index   = FAISSIndex(document_id, dimension=self.dimension)
            faiss_matches = text_index.search(query_vector, top_k=stage_k)
            faiss_scores  = {uid: score for uid, score in faiss_matches if score > 0}
            logger.info(f"  [FAISS] {len(faiss_scores)} matches.")
        except Exception as e:
            logger.warning(f"FAISS retrieval failed (skipping): {e}")

        # ── Stage 3: CLIP Visual Search ───────────────────────────────────
        clip_scores: Dict[str, float] = {}
        if settings.enable_clip:
            try:
                clip_faiss = FAISSIndex(
                    document_id,
                    dimension=settings.clip_embedding_dim,
                    suffix="_clip"
                )
                if clip_faiss.vector_count > 0:
                    clip_engine    = self._get_clip()
                    query_clip_vec = clip_engine.encode_text(query) if clip_engine else None
                    if query_clip_vec is not None:
                        clip_matches = clip_faiss.search(query_clip_vec, top_k=stage_k)
                        clip_scores  = {uid: score for uid, score in clip_matches if score > 0}
                        logger.info(f"  [CLIP]  {len(clip_scores)} visual matches.")
            except Exception as e:
                logger.warning(f"CLIP retrieval failed (skipping): {e}")

        # ── Stage 4: LayoutLMv3 Search (optional) ─────────────────────────
        layoutlm_scores: Dict[str, float] = {}
        if settings.enable_layoutlm:
            try:
                lm_faiss = FAISSIndex(
                    document_id,
                    dimension=settings.layoutlm_embedding_dim,
                    suffix="_layoutlm"
                )
                if lm_faiss.vector_count > 0:
                    # Reuse text query vector approximation for retrieval
                    lm_matches    = lm_faiss.search(query_vector[:settings.layoutlm_embedding_dim]
                                                    if len(query_vector) >= settings.layoutlm_embedding_dim
                                                    else np.pad(query_vector, (0, settings.layoutlm_embedding_dim - len(query_vector))),
                                                    top_k=stage_k)
                    layoutlm_scores = {uid: s for uid, s in lm_matches if s > 0}
                    logger.info(f"  [LayoutLM] {len(layoutlm_scores)} matches.")
            except Exception as e:
                logger.warning(f"LayoutLMv3 retrieval failed (skipping): {e}")

        # ── Stage 5: Weighted Score Fusion ────────────────────────────────
        all_chunk_ids = (
            set(bm25_scores)
            | set(faiss_scores)
            | set(clip_scores)
            | set(layoutlm_scores)
        )

        if not all_chunk_ids:
            logger.warning("All retrieval stages returned zero results.")
            return []

        fused: Dict[str, Dict] = {}
        for cid in all_chunk_ids:
            s_bm25  = bm25_scores.get(cid, 0.0)
            s_faiss = faiss_scores.get(cid, 0.0)
            s_clip  = clip_scores.get(cid, 0.0)
            s_lm    = layoutlm_scores.get(cid, 0.0)

            combined = (
                settings.bm25_weight  * s_bm25
                + settings.faiss_weight * s_faiss
                + settings.clip_weight  * s_clip
                + (0.2 * s_lm if settings.enable_layoutlm else 0.0)
            )

            # Label the primary retrieval source (highest contributing stage)
            stage_contributions = {
                "bm25":       s_bm25  * settings.bm25_weight,
                "semantic":   s_faiss * settings.faiss_weight,
                "visual":     s_clip  * settings.clip_weight,
                "multimodal": s_lm    * 0.2,
            }
            # "hybrid" if found by multiple stages, otherwise the dominant stage
            active_stages = [k for k, v in stage_contributions.items() if v > 0]
            if len(active_stages) > 1:
                source = "hybrid"
            elif active_stages:
                source = active_stages[0]
            else:
                source = "semantic"

            fused[cid] = {
                "combined_score": combined,
                "bm25_score":     s_bm25,
                "faiss_score":    s_faiss,
                "clip_score":     s_clip,
                "source":         source,
            }

        # Sort by combined score (descending), take top_k
        ranked = sorted(fused.items(), key=lambda x: x[1]["combined_score"], reverse=True)
        ranked = ranked[:top_k]
        logger.info(f"  [Fusion] {len(ranked)} results after score fusion.")

        # ── Stage 6: Fetch Chunk metadata from SQLite ─────────────────────
        top_ids = [cid for cid, _ in ranked]
        db_chunks = db.query(Chunk).filter(Chunk.id.in_(top_ids)).all()
        chunk_map = {c.id: c for c in db_chunks}

        return self._format_evidence(ranked, chunk_map, document_id)

    def _faiss_only_retrieve(
        self,
        db: Session,
        document_id: str,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Legacy FAISS-only retrieval path (v1.0 behavior)."""
        embedder     = self._get_embedder()
        query_vector = embedder.encode(query, convert_to_numpy=True)

        text_index = FAISSIndex(document_id, dimension=self.dimension)
        matches    = text_index.search(query_vector, top_k=top_k)

        if not matches:
            return []

        chunk_ids = [uid for uid, _ in matches]
        scores    = {uid: score for uid, score in matches}
        db_chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
        db_chunks.sort(key=lambda c: chunk_ids.index(c.id))

        ranked = [(c.id, {"combined_score": scores[c.id], "bm25_score": 0.0,
                           "faiss_score": scores[c.id], "clip_score": 0.0,
                           "source": "semantic"})
                  for c in db_chunks]
        chunk_map = {c.id: c for c in db_chunks}
        return self._format_evidence(ranked, chunk_map, document_id)

    def _format_evidence(
        self,
        ranked: List[Tuple[str, Dict]],
        chunk_map: Dict[str, Chunk],
        document_id: str
    ) -> List[Dict[str, Any]]:
        """
        Format ranked results into the standard evidence schema.
        Builds image_url for figure/table chunks (lazy crop API).
        """
        evidence = []
        for chunk_id, scores in ranked:
            chunk = chunk_map.get(chunk_id)
            if chunk is None:
                continue

            image_url = None
            if chunk.chunk_type in ("figure", "table") and chunk.image_path:
                image_url = (
                    f"http://localhost:8000/api/documents/{document_id}/figure/{chunk.id}"
                )

            evidence.append({
                "chunk_id":         chunk.id,
                "chunk_type":       chunk.chunk_type,
                "page_number":      chunk.page_number,
                "section_title":    chunk.section_title,
                "snippet":          chunk.content,
                "image_url":        image_url,
                "relevance_score":  scores["combined_score"],
                "retrieval_source": scores["source"],
                "layout_label":     chunk.layout_label,
                "bm25_score":       scores.get("bm25_score"),
                "faiss_score":      scores.get("faiss_score"),
                "clip_score":       scores.get("clip_score"),
                "bbox":             chunk.bbox,
            })

        return evidence
