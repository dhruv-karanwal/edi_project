"""
Feature 5: LayoutLMv3 Multimodal Document Understanding (Optional)

LayoutLMv3 from Microsoft is a transformer model that jointly reasons over:
  - Document text        (word tokens)
  - Spatial layout       (2D bounding boxes)
  - Visual appearance    (page image patch features)

This produces superior chunk representations compared to text-only
SentenceTransformer embeddings for document-heavy tasks.

⚠️  IMPORTANT — Performance Warning:
    Model size:        ~900 MB (downloaded once from HuggingFace)
    CPU inference:     ~30–60 seconds per page
    GPU inference:     ~1–2 seconds per page

    This feature is DISABLED by default (ENABLE_LAYOUTLM=false).
    Enable it only for:
      - GPU-enabled environments
      - Single-page analysis
      - Offline batch processing without latency requirements

Architecture:
    chunk (text + bbox + page_image)
         ↓
    LayoutLMv3Processor  →  tokenized encoding with spatial coords
         ↓
    LayoutLMv3Model      →  contextual hidden states
         ↓
    CLS token [0]        →  768-dim multimodal embedding
         ↓
    Stored in {doc_id}_layoutlm.index (FAISSIndex, dim=768)
"""

import os
import numpy as np
from typing import Optional, List, Dict, Any
from PIL import Image
from utils.logger import logger
from config import get_settings

settings = get_settings()


class LayoutLMEngine:
    """
    Generates LayoutLMv3 multimodal embeddings from document chunks.

    Each embedding captures text semantics, bounding-box layout context,
    and visual page patch features simultaneously, giving richer
    representations than text-only or image-only models.

    Usage (when ENABLE_LAYOUTLM=true):
        engine = LayoutLMEngine()
        embedding = engine.generate_embedding(chunk, page_image_path)
    """

    def __init__(self):
        self._processor  = None     # LayoutLMv3Processor
        self._model      = None     # LayoutLMv3Model
        self._available  = None     # None = unchecked, True/False = resolved

    def _load_model(self) -> bool:
        """
        Lazily initialise LayoutLMv3 processor and model.
        Downloads from HuggingFace on first use (~900 MB).
        """
        if self._available is False:
            return False
        if self._model is not None:
            return True

        if not settings.enable_layoutlm:
            self._available = False
            return False

        try:
            from transformers import LayoutLMv3Processor, LayoutLMv3Model

            logger.info(
                f"Loading LayoutLMv3 model: {settings.layoutlm_model} "
                f"— first use will download ~900MB from HuggingFace..."
            )
            self._processor = LayoutLMv3Processor.from_pretrained(
                settings.layoutlm_model,
                apply_ocr=False  # We supply our own words+boxes; no internal OCR
            )
            self._model = LayoutLMv3Model.from_pretrained(settings.layoutlm_model)
            self._model.eval()

            self._available = True
            logger.info("LayoutLMv3 model loaded successfully.")
            return True

        except ImportError:
            logger.warning(
                "transformers package not found. LayoutLMv3 disabled. "
                "Install with: pip install transformers"
            )
            self._available = False
            return False

        except Exception as e:
            logger.error(f"Failed to load LayoutLMv3 model: {e}")
            self._available = False
            return False

    def generate_embedding(
        self,
        chunk: Dict[str, Any],
        page_image_path: str
    ) -> Optional[np.ndarray]:
        """
        Generate a 768-dim multimodal embedding for a document chunk.

        The embedding combines:
          - Tokenized chunk text
          - Normalized bounding box coordinates (0-1000 grid)
          - Visual patch features from the parent page image

        Args:
            chunk:           Internal chunk dict with 'content' and 'bbox'.
            page_image_path: Path to the rendered PNG of the parent page.

        Returns:
            np.ndarray of shape (768,) in float32, or None on failure.
        """
        if not self._load_model():
            return None

        try:
            import torch

            content = chunk.get("content", "")
            bbox    = chunk.get("bbox")

            # Tokenize the chunk content into words
            words = content.split()
            if not words:
                words = ["[EMPTY]"]

            # If a bounding box is available, use it; otherwise fill the full page
            if bbox and all(k in bbox for k in ("x0", "y0", "x1", "y1")):
                # LayoutLMv3 expects integer coordinates in [0, 1000]
                chunk_bbox = [
                    int(bbox["x0"]), int(bbox["y0"]),
                    int(bbox["x1"]), int(bbox["y1"])
                ]
            else:
                chunk_bbox = [0, 0, 1000, 1000]  # Full page fallback

            # Assign the same bounding box to every word token
            word_boxes = [chunk_bbox] * len(words)

            # Load the page image for visual features
            if page_image_path and os.path.exists(page_image_path):
                page_image = Image.open(page_image_path).convert("RGB")
            else:
                # Blank white image as fallback when page image is unavailable
                page_image = Image.new("RGB", (224, 224), color=(255, 255, 255))

            # Run through LayoutLMv3 processor
            encoding = self._processor(
                images=page_image,
                text=words,
                boxes=word_boxes,
                return_tensors="pt",
                padding="max_length",
                truncation=True,
                max_length=512
            )

            # Forward pass through the transformer
            with torch.no_grad():
                outputs = self._model(**encoding)

            # Extract the CLS token hidden state as the chunk representation
            # Shape: [batch=1, seq_len, hidden=768] → take [0, 0, :] = CLS
            cls_embedding = outputs.last_hidden_state[0, 0, :].detach().numpy()
            cls_embedding = cls_embedding.astype(np.float32)

            # L2 normalize for cosine-similarity-compatible FAISS search
            norm = np.linalg.norm(cls_embedding)
            if norm > 0:
                cls_embedding = cls_embedding / norm

            return cls_embedding  # shape: (768,)

        except Exception as e:
            logger.error(f"LayoutLMv3 embedding generation failed: {e}")
            return None

    def generate_batch_embeddings(
        self,
        chunks: List[Dict[str, Any]],
        page_image_path: str
    ) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple chunks sharing the same parent page.

        Args:
            chunks:          List of chunk dicts.
            page_image_path: Path to the rendered parent page PNG.

        Returns:
            List of embeddings (or None for failed items).
        """
        return [self.generate_embedding(chunk, page_image_path) for chunk in chunks]

    @property
    def is_available(self) -> bool:
        """True if LayoutLMv3 model is loaded and ready."""
        return self._available is True
