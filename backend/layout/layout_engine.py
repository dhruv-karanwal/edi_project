"""
Feature 2: AI Layout Detection Engine (surya-ocr v0.17+)

Uses surya's FoundationPredictor + LayoutPredictor to identify semantic
document regions (title, paragraph, figure, table, caption, formula, etc.)
from rendered page images. Fully Windows-compatible and CPU-native.

surya 0.17.x API:
    foundation_predictor = FoundationPredictor(checkpoint=...)
    layout_predictor = LayoutPredictor(foundation_predictor)
    results = layout_predictor([pil_image])  → List[LayoutResult]
    result.bboxes → List[LayoutBox]
    LayoutBox.bbox   → [x_min, y_min, x_max, y_max] in pixel coords
    LayoutBox.label  → str (e.g. "Title", "Figure", "Table", ...)
    LayoutBox.confidence → float [0, 1]
    result.image_bbox → [0, 0, img_width, img_height]

Layout label → chunk_type mapping:
  Title / Section-header / Page-header  → "text"  (section_title=label)
  Text / List-item / Footnote            → "text"
  Figure / Picture                       → "figure"
  Table                                  → "table"
  Caption                                → "caption"
  Formula                                → "equation"
  Page-footer                            → "text"  (low priority)
"""

from typing import List, Dict, Any, Optional
from PIL import Image
from utils.logger import logger
from config import get_settings

settings = get_settings()


# ── Label classification sets ─────────────────────────────────────────────────
_TITLE_LABELS    = {"Title", "Section-header", "Page-header"}
_TEXT_LABELS     = {"Text", "List-item", "Footnote", "Page-footer"}
_FIGURE_LABELS   = {"Figure", "Picture"}
_TABLE_LABELS    = {"Table"}
_CAPTION_LABELS  = {"Caption"}
_EQUATION_LABELS = {"Formula"}


def _map_surya_label(label: str) -> str:
    """Map a surya region label string to the internal chunk_type."""
    if label in _TITLE_LABELS:
        return "text"
    if label in _FIGURE_LABELS:
        return "figure"
    if label in _TABLE_LABELS:
        return "table"
    if label in _CAPTION_LABELS:
        return "caption"
    if label in _EQUATION_LABELS:
        return "equation"
    return "text"  # default for Text / List-item / etc.


class LayoutEngine:
    """
    AI-powered document layout detection using surya-ocr.

    Lazy-loads the surya FoundationPredictor + LayoutPredictor on first use
    to avoid heavy model loading during server startup.

    Falls back gracefully (returns None) if surya is not available or if
    detection fails, signalling pdf_service to use heuristic extraction.
    """

    def __init__(self):
        self._foundation   = None    # surya FoundationPredictor
        self._predictor    = None    # surya LayoutPredictor
        self._available    = None    # None = unchecked, True/False = resolved

    def _load_predictor(self):
        """
        Lazily initialise the surya layout detection stack.

        surya 0.17+ requires two steps:
          1. FoundationPredictor (loads the foundation model + processor)
          2. LayoutPredictor (wraps foundation with layout-specific logic)
        """
        if self._available is False:
            return False
        if self._predictor is not None:
            return True

        try:
            from surya.foundation import FoundationPredictor
            from surya.layout import LayoutPredictor
            from surya.settings import settings as surya_settings

            logger.info(
                "Loading surya FoundationPredictor for layout detection "
                "(first use — may take a moment to download models)..."
            )
            self._foundation = FoundationPredictor(
                checkpoint=surya_settings.LAYOUT_MODEL_CHECKPOINT
            )
            self._predictor = LayoutPredictor(self._foundation)
            self._available = True
            logger.info("surya LayoutPredictor loaded successfully.")
            return True

        except ImportError:
            logger.warning(
                "surya-ocr is not installed or not importable. "
                "AI layout detection disabled — falling back to heuristics. "
                "Install with: pip install surya-ocr"
            )
            self._available = False
            return False

        except Exception as e:
            logger.error(f"Failed to load surya LayoutPredictor: {e}")
            self._available = False
            return False

    def detect_layout(
        self,
        image_path: str,
        page_number: int,
        page_image_path: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Run AI layout detection on a rendered page image.

        Args:
            image_path:      Absolute path to the page PNG image.
            page_number:     1-indexed page number (for metadata).
            page_image_path: Parent page image path stored in chunk metadata.

        Returns:
            List of chunk dicts (internal schema), or None to signal fallback.

        Chunk schema:
            chunk_type:        str   — "text"|"figure"|"table"|"caption"|"equation"
            content:           str   — descriptive placeholder (text via OCR/native)
            page_number:       int
            section_title:     str | None
            caption:           str | None
            bbox:              dict  — {x0, y0, x1, y1} normalized to 0-1000
            image_path:        str
            layout_label:      str   — raw surya label (e.g. "Title", "Figure")
            layout_confidence: float — detection confidence [0, 1]
        """
        if not self._load_predictor():
            return None

        try:
            image = Image.open(image_path).convert("RGB")
            img_width, img_height = image.size

            logger.info(f"Running surya AI layout detection on page {page_number}...")

            # Run inference — surya 0.17 takes a list of PIL images
            results = self._predictor([image])

            if not results:
                logger.warning(f"surya returned empty results for page {page_number}.")
                return None

            layout_result = results[0]

            # image_bbox = [0, 0, img_width, img_height] — used for normalization
            iw = layout_result.image_bbox[2] if layout_result.image_bbox[2] > 0 else img_width
            ih = layout_result.image_bbox[3] if layout_result.image_bbox[3] > 0 else img_height

            chunks = []
            for bbox_obj in layout_result.bboxes:
                # bbox is a computed property: [x_min, y_min, x_max, y_max] in pixel coords
                raw_bbox = bbox_obj.bbox           # [x0, y0, x1, y1]
                label    = bbox_obj.label          # str, e.g. "Title"
                conf     = bbox_obj.confidence or 1.0  # float [0,1]

                # Normalize pixel coords → 0-1000 relative grid
                rx0 = (raw_bbox[0] / iw) * 1000
                ry0 = (raw_bbox[1] / ih) * 1000
                rx1 = (raw_bbox[2] / iw) * 1000
                ry1 = (raw_bbox[3] / ih) * 1000

                # Clamp to valid range
                rx0 = max(0.0, min(rx0, 1000.0))
                ry0 = max(0.0, min(ry0, 1000.0))
                rx1 = max(0.0, min(rx1, 1000.0))
                ry1 = max(0.0, min(ry1, 1000.0))

                chunk_type    = _map_surya_label(label)
                is_title      = label in _TITLE_LABELS
                section_title = label if is_title else None

                # Content placeholder — actual text enriched separately via native PDF / OCR
                if chunk_type == "figure":
                    content = f"[AI-detected figure on page {page_number}]"
                elif chunk_type == "table":
                    content = f"[AI-detected table on page {page_number}]"
                elif chunk_type == "equation":
                    content = f"[AI-detected formula on page {page_number}]"
                elif chunk_type == "caption":
                    content = f"[AI-detected caption on page {page_number}]"
                elif is_title:
                    content = f"[AI-detected {label} on page {page_number}]"
                else:
                    content = f"[AI-detected text region on page {page_number}]"

                chunks.append({
                    "chunk_type":          chunk_type,
                    "content":             content,
                    "page_number":         page_number,
                    "section_title":       section_title,
                    "caption":             None,
                    "bbox":                {"x0": rx0, "y0": ry0, "x1": rx1, "y1": ry1},
                    "image_path":          page_image_path,
                    "layout_label":        label,
                    "layout_confidence":   float(conf),
                })

            logger.info(
                f"surya AI layout: {len(chunks)} regions detected on page {page_number}."
            )
            return chunks if chunks else None

        except Exception as e:
            logger.error(
                f"surya layout detection error on page {page_number}: {e}", exc_info=True
            )
            return None
