"""
PDF Processing Service — v2.0

Natively parses PDF layouts, renders page images, and crops grounded
evidence regions.

v2.0 Changes:
  - extract_layout() now tries surya AI layout detection first
    (when ENABLE_LAYOUT_DETECTION=true) and falls back to the existing
    PyMuPDF heuristic block parser if detection fails or is disabled.
  - Layout chunks carry new fields: layout_label, layout_confidence
"""

import os
import fitz  # PyMuPDF
from PIL import Image
from typing import List, Dict, Any
from config import get_settings
from utils.logger import logger
from ocr.ocr_engine import OCREngine

settings = get_settings()


class PDFService:
    """
    Handles all PDF-level operations:
      - Page rasterization (PyMuPDF, no Poppler dependency)
      - Layout extraction (AI-powered or heuristic fallback)
      - On-demand figure cropping (lazy, normalized 0-1000 grid)
    """

    def __init__(self):
        self.ocr_engine   = OCREngine()
        self._layout_engine = None   # surya LayoutEngine — lazily created

    def _get_layout_engine(self):
        """Lazily instantiate the surya LayoutEngine."""
        if self._layout_engine is None:
            from layout.layout_engine import LayoutEngine
            self._layout_engine = LayoutEngine()
        return self._layout_engine

    # ── Page Rendering ────────────────────────────────────────────────────────

    def render_pages(self, pdf_path: str) -> List[str]:
        """
        Render each PDF page as a high-resolution PNG image.

        Uses PyMuPDF's built-in C-based rasterizer at 2× zoom.
        Zero external dependencies — no Poppler required.

        Returns:
            List of absolute PNG file paths (one per page).
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found at: {pdf_path}")

        doc       = fitz.open(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        page_paths: List[str] = []

        logger.info(f"Rendering {len(doc)} pages for: {base_name}")

        for page_num in range(len(doc)):
            page = doc[page_num]
            # 2× zoom matrix for high-quality rendering
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            filename  = f"{base_name}_page_{page_num + 1}.png"
            page_path = os.path.join(settings.pages_dir, filename)
            pix.save(page_path)
            page_paths.append(page_path)

        doc.close()
        logger.info(f"Rendered {len(page_paths)} pages.")
        return page_paths

    # ── Layout Extraction ─────────────────────────────────────────────────────

    def extract_layout(
        self,
        pdf_path: str,
        page_images: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured layout chunks from a PDF.

        v2.0 Strategy (per page):
          1. If ENABLE_LAYOUT_DETECTION=true  → try surya AI layout detection
          2. If surya returns regions           → use AI results
          3. Otherwise                          → fall back to PyMuPDF heuristics

        All chunks share the same schema regardless of extraction path:
          chunk_type, content, page_number, section_title, caption,
          bbox (0-1000 normalized), image_path,
          layout_label (v2.0), layout_confidence (v2.0)

        Returns:
            Flat list of chunk dicts across all pages.
        """
        doc    = fitz.open(pdf_path)
        chunks: List[Dict[str, Any]] = []

        for page_num in range(len(doc)):
            page            = doc[page_num]
            page_width      = page.rect.width
            page_height     = page.rect.height
            page_image_path = page_images[page_num]

            page_chunks: List[Dict[str, Any]] = []

            # ── Try AI Layout Detection ──────────────────────────────────────
            if settings.enable_layout_detection:
                try:
                    engine      = self._get_layout_engine()
                    ai_chunks   = engine.detect_layout(
                        image_path      = page_image_path,
                        page_number     = page_num + 1,
                        page_image_path = page_image_path
                    )

                    if ai_chunks:
                        logger.info(
                            f"Page {page_num + 1}: Using AI layout "
                            f"({len(ai_chunks)} regions detected)."
                        )
                        # For text-type AI regions, enrich content via OCR
                        # (AI layout gives bounding boxes; actual text comes from native or OCR)
                        page_chunks = self._enrich_ai_chunks_with_text(
                            ai_chunks, page, page_width, page_height, page_image_path, page_num
                        )
                    else:
                        logger.info(
                            f"Page {page_num + 1}: AI layout returned no regions — "
                            f"falling back to heuristics."
                        )
                except Exception as e:
                    logger.warning(
                        f"Page {page_num + 1}: AI layout error ({e}) — "
                        f"falling back to heuristics."
                    )

            # ── Fall back to PyMuPDF Heuristic Extraction ────────────────────
            if not page_chunks:
                page_chunks = self._extract_heuristic(
                    page, page_width, page_height, page_image_path, page_num
                )

            chunks.extend(page_chunks)

        doc.close()
        logger.info(f"Total chunks extracted: {len(chunks)}")
        return chunks

    def _enrich_ai_chunks_with_text(
        self,
        ai_chunks: List[Dict[str, Any]],
        page,
        page_width: float,
        page_height: float,
        page_image_path: str,
        page_num: int
    ) -> List[Dict[str, Any]]:
        """
        For AI-detected text regions, replace the placeholder content with
        actual text extracted from the underlying PyMuPDF page.

        For figure/table/equation regions, the placeholder is kept
        (visual content is handled by the CLIP indexing pipeline).
        """
        enriched = []

        # Get all native text blocks for matching
        blocks     = page.get_text("blocks")
        raw_text   = page.get_text().strip()
        use_ocr    = len(raw_text) < 150

        for chunk in ai_chunks:
            if chunk["chunk_type"] in ("figure", "table", "equation", "caption"):
                # Keep placeholder — visual content is indexed via CLIP
                enriched.append(chunk)
                continue

            # For text/section regions: extract actual text within the bounding box
            bbox    = chunk.get("bbox")
            content = self._extract_text_in_bbox(page, bbox, page_width, page_height)

            if not content and use_ocr:
                # Sparse page — run OCR on the full page image
                try:
                    ocr_blocks = self.ocr_engine.perform_ocr(page_image_path)
                    # Find OCR blocks overlapping this region
                    content = self._find_overlapping_ocr_text(ocr_blocks, bbox)
                except Exception:
                    pass

            if content:
                chunk = dict(chunk)   # shallow copy to avoid mutation
                chunk["content"] = content
            # else: keep AI placeholder content

            enriched.append(chunk)

        return enriched

    def _extract_text_in_bbox(
        self,
        page,
        bbox: Dict[str, float],
        page_width: float,
        page_height: float
    ) -> str:
        """
        Extract native PDF text within a normalized 0-1000 bounding box region.
        """
        if not bbox:
            return ""
        try:
            # Convert 0-1000 normalized coords back to PDF points
            rect = fitz.Rect(
                (bbox["x0"] / 1000) * page_width,
                (bbox["y0"] / 1000) * page_height,
                (bbox["x1"] / 1000) * page_width,
                (bbox["y1"] / 1000) * page_height,
            )
            return page.get_text("text", clip=rect).strip()
        except Exception:
            return ""

    def _find_overlapping_ocr_text(
        self,
        ocr_blocks: List[Dict],
        target_bbox: Dict[str, float]
    ) -> str:
        """Find OCR text blocks that overlap with the target normalized bounding box."""
        if not target_bbox or not ocr_blocks:
            return ""

        collected = []
        for block in ocr_blocks:
            b = block.get("bbox", {})
            # Simple centroid check for overlap
            cx = (b.get("x0", 0) + b.get("x1", 0)) / 2
            cy = (b.get("y0", 0) + b.get("y1", 0)) / 2
            if (target_bbox["x0"] <= cx <= target_bbox["x1"] and
                    target_bbox["y0"] <= cy <= target_bbox["y1"]):
                collected.append(block["text"])

        return " ".join(collected)

    def _extract_heuristic(
        self,
        page,
        page_width: float,
        page_height: float,
        page_image_path: str,
        page_num: int
    ) -> List[Dict[str, Any]]:
        """
        Original PyMuPDF heuristic block extraction (v1.0 behavior).
        Used as fallback when AI layout detection is disabled or fails.
        """
        chunks: List[Dict[str, Any]] = []
        blocks   = page.get_text("blocks")
        raw_text = page.get_text().strip()

        # ── Scanned / sparse page → run OCR pipeline ─────────────────────────
        if len(raw_text) < 150:
            logger.info(
                f"Page {page_num + 1}: low native text ({len(raw_text)} chars) → OCR."
            )
            try:
                ocr_blocks = self.ocr_engine.perform_ocr(page_image_path)
                for ob in ocr_blocks:
                    chunks.append({
                        "chunk_type":         "text",
                        "content":            ob["text"],
                        "page_number":        page_num + 1,
                        "section_title":      "Scanned Document Content",
                        "caption":            None,
                        "bbox":               ob["bbox"],
                        "image_path":         page_image_path,
                        "layout_label":       None,
                        "layout_confidence":  None,
                    })
            except Exception as e:
                logger.error(f"OCR failed on page {page_num + 1}: {e}")
            return chunks

        # ── Native text page → parse PyMuPDF blocks ───────────────────────────
        logger.info(f"Page {page_num + 1}: native text — parsing {len(blocks)} blocks.")

        for block in blocks:
            bx0, by0, bx1, by1, btext, bnum, btype = block
            btext = btext.strip()
            if not btext:
                continue

            rx0 = (bx0 / page_width)  * 1000
            ry0 = (by0 / page_height) * 1000
            rx1 = (bx1 / page_width)  * 1000
            ry1 = (by1 / page_height) * 1000

            chunk_type    = "text"
            section_title = None
            lower_text    = btext.lower()

            # Heuristic classification
            if len(btext) < 100 and any(kw in lower_text for kw in ["figure ", "fig. ", "fig "]):
                chunk_type = "caption"
            elif len(btext) < 100 and any(kw in lower_text for kw in ["table ", "tbl "]):
                chunk_type = "caption"
            elif len(btext) < 150 and (btext.isupper() or btext.istitle() or btext[0].isdigit()):
                section_title = btext.split('\n')[0]

            chunks.append({
                "chunk_type":         chunk_type,
                "content":            btext,
                "page_number":        page_num + 1,
                "section_title":      section_title,
                "caption":            btext if chunk_type == "caption" else None,
                "bbox":               {"x0": rx0, "y0": ry0, "x1": rx1, "y1": ry1},
                "image_path":         page_image_path,
                "layout_label":       None,
                "layout_confidence":  None,
            })

        # ── Tables ────────────────────────────────────────────────────────────
        tabs = page.find_tables()
        for tab in tabs:
            tx0, ty0, tx1, ty1 = tab.bbox
            table_data = tab.extract()
            table_str  = "\n".join(
                [" | ".join([cell or "" for cell in row]) for row in table_data]
            )
            chunks.append({
                "chunk_type":         "table",
                "content":            f"Table structure data:\n{table_str}",
                "page_number":        page_num + 1,
                "section_title":      "Tabular Data Extraction",
                "caption":            None,
                "bbox":               {
                    "x0": (tx0 / page_width)  * 1000,
                    "y0": (ty0 / page_height) * 1000,
                    "x1": (tx1 / page_width)  * 1000,
                    "y1": (ty1 / page_height) * 1000,
                },
                "image_path":         page_image_path,
                "layout_label":       None,
                "layout_confidence":  None,
            })

        # ── Embedded Images (figures) ─────────────────────────────────────────
        for img in page.get_images():
            xref  = img[0]
            rects = page.get_image_rects(xref)
            for rect in rects:
                ix0, iy0, ix1, iy1 = rect
                chunks.append({
                    "chunk_type":         "figure",
                    "content":            f"Visual component on page {page_num + 1}",
                    "page_number":        page_num + 1,
                    "section_title":      "Visual Figure Extraction",
                    "caption":            None,
                    "bbox":               {
                        "x0": (ix0 / page_width)  * 1000,
                        "y0": (iy0 / page_height) * 1000,
                        "x1": (ix1 / page_width)  * 1000,
                        "y1": (iy1 / page_height) * 1000,
                    },
                    "image_path":         page_image_path,
                    "layout_label":       None,
                    "layout_confidence":  None,
                })

        return chunks

    # ── Figure Cropping ───────────────────────────────────────────────────────

    def crop_region(
        self,
        page_image_path: str,
        bbox: Dict[str, float],
        output_path: str
    ) -> bool:
        """
        Lazily crop a figure region from a rendered page PNG.

        Converts the normalized 0-1000 bounding box back to pixel coordinates,
        adds a 10-pixel padding, and saves the crop as a PNG.

        Returns:
            True if crop was saved successfully, False otherwise.
        """
        try:
            if not os.path.exists(page_image_path):
                return False

            image         = Image.open(page_image_path)
            width, height = image.size

            # Map 0-1000 grid → actual pixels
            px0 = (bbox["x0"] / 1000) * width
            py0 = (bbox["y0"] / 1000) * height
            px1 = (bbox["x1"] / 1000) * width
            py1 = (bbox["y1"] / 1000) * height

            # Add padding to prevent overly tight crops
            padding = 10
            px0 = max(0,     px0 - padding)
            py0 = max(0,     py0 - padding)
            px1 = min(width, px1 + padding)
            py1 = min(height, py1 + padding)

            if (px1 - px0) > 5 and (py1 - py0) > 5:
                cropped = image.crop((px0, py0, px1, py1))
                cropped.save(output_path)
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to crop region: {e}")
            return False
