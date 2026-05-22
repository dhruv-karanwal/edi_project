"""
Feature 3: CLIP Image Embeddings for Visual Semantic Retrieval

Uses OpenAI's CLIP model (via open_clip_torch) to generate 512-dimensional
embeddings for both document figures/tables AND text queries.

This enables cross-modal retrieval: a user can describe a figure in natural
language and the system can find visually matching content even when the
text surrounding the figure is sparse or absent.

Architecture:
  ┌──────────────────────────────────────┐
  │        CLIPEngine                    │
  │  ┌────────────────┐  ┌────────────┐  │
  │  │ encode_image() │  │encode_text()│  │
  │  └───────┬────────┘  └─────┬──────┘  │
  │          │                 │          │
  │          └──────┬──────────┘          │
  │                 ▼                     │
  │         512-dim L2-norm vector        │
  └──────────────────────────────────────┘
                   │
          Stored in FAISSIndex
          ({doc_id}_clip.index)

CPU inference note:
  CLIP ViT-B-32 runs comfortably on CPU (~0.5s per image).
  torch.amp.autocast is used for mixed-precision where available.
"""

import os
import numpy as np
from typing import Optional, List, Tuple
from PIL import Image
from utils.logger import logger
from config import get_settings

settings = get_settings()


class CLIPEngine:
    """
    Generates CLIP visual and text embeddings for cross-modal document retrieval.

    Model: openai/ViT-B-32 via open_clip_torch (512-dim embeddings)

    Lazy loading: The 350MB model is only downloaded and initialized on the
    first call to encode_image() or encode_text(), reducing startup overhead.
    """

    def __init__(self):
        self._model      = None     # open_clip model
        self._preprocess = None     # image preprocessing transform
        self._tokenizer  = None     # text tokenizer
        self._available  = None     # None = unchecked, True/False = resolved

    def _load_model(self):
        """
        Lazily load the CLIP model, preprocessing pipeline, and tokenizer.
        Sets self._available = False permanently on failure.
        """
        if self._available is False:
            return False
        if self._model is not None:
            return True

        try:
            import open_clip
            import torch

            logger.info(
                f"Loading CLIP model: {settings.clip_model} "
                f"(pretrained={settings.clip_pretrained}) — first use may download ~350MB..."
            )
            self._model, _, self._preprocess = open_clip.create_model_and_transforms(
                settings.clip_model,
                pretrained=settings.clip_pretrained
            )
            self._tokenizer = open_clip.get_tokenizer(settings.clip_model)

            # Keep model in eval mode for inference
            self._model.eval()
            self._available = True
            logger.info("CLIP model loaded successfully (CPU mode).")
            return True

        except ImportError:
            logger.warning(
                "open_clip_torch is not installed. CLIP visual retrieval disabled. "
                "Install with: pip install open_clip_torch"
            )
            self._available = False
            return False

        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            self._available = False
            return False

    def encode_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        Generate a 512-dim L2-normalized CLIP embedding for an image file.

        Args:
            image_path: Absolute path to a PNG/JPEG image.

        Returns:
            np.ndarray of shape (512,) in float32, or None on failure.
        """
        if not self._load_model():
            return None

        if not os.path.exists(image_path):
            logger.warning(f"CLIP encode_image: file not found: {image_path}")
            return None

        try:
            import torch

            image = Image.open(image_path).convert("RGB")
            # Apply the CLIP preprocessing transform (resize, normalize, etc.)
            image_tensor = self._preprocess(image).unsqueeze(0)  # shape: [1, 3, 224, 224]

            with torch.no_grad():
                # autocast improves speed on supported CPU/GPU
                with torch.amp.autocast("cpu"):
                    features = self._model.encode_image(image_tensor)

            # L2 normalize so dot-product == cosine similarity
            features = features / features.norm(dim=-1, keepdim=True)
            return features.numpy().astype(np.float32)[0]  # shape: (512,)

        except Exception as e:
            logger.error(f"CLIP image encoding failed for {image_path}: {e}")
            return None

    def encode_text(self, text: str) -> Optional[np.ndarray]:
        """
        Generate a 512-dim L2-normalized CLIP embedding for a text query.

        This allows text-to-image retrieval: the query embedding can be
        compared directly against stored figure embeddings.

        Args:
            text: Natural language query string.

        Returns:
            np.ndarray of shape (512,) in float32, or None on failure.
        """
        if not self._load_model():
            return None

        try:
            import torch

            # Tokenize and truncate to CLIP's 77-token context length
            tokens = self._tokenizer([text])  # shape: [1, 77]

            with torch.no_grad():
                with torch.amp.autocast("cpu"):
                    features = self._model.encode_text(tokens)

            features = features / features.norm(dim=-1, keepdim=True)
            return features.numpy().astype(np.float32)[0]  # shape: (512,)

        except Exception as e:
            logger.error(f"CLIP text encoding failed: {e}")
            return None

    @property
    def is_available(self) -> bool:
        """True if CLIP model was successfully loaded."""
        return self._available is True

    def encode_image_batch(self, image_paths: List[str]) -> List[Optional[np.ndarray]]:
        """
        Encode a list of image files in sequence.

        Args:
            image_paths: List of absolute image file paths.

        Returns:
            List of 512-dim vectors (or None for failed items).
        """
        return [self.encode_image(p) for p in image_paths]
