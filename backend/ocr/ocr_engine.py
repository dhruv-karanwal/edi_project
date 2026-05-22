import os
import numpy as np
import pytesseract
from PIL import Image
from typing import List, Dict, Any
from utils.logger import logger
from config import get_settings

settings = get_settings()


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 1: OpenCV OCR Enhancement Pipeline
# ══════════════════════════════════════════════════════════════════════════════

class ImagePreprocessor:
    """
    Applies an OpenCV-based image enhancement pipeline to improve OCR quality
    on scanned, noisy, or skewed document images.

    Pipeline stages (all configurable):
      1. Grayscale conversion      — reduces colour noise
      2. Denoising                 — Non-Local Means removes grain/JPEG artifacts
      3. Deskewing                 — corrects rotated scans via moments analysis
      4. Adaptive thresholding     — binarises the image for clean black/white text
      5. Sharpening                — sharpens text edges via unsharp-mask kernel
    """

    def preprocess(self, image: Image.Image) -> Image.Image:
        """
        Run the full preprocessing pipeline on a PIL Image.

        Args:
            image: Input PIL image (any mode).

        Returns:
            Preprocessed PIL Image suitable for OCR.
        """
        try:
            import cv2  # lazy import — only needed when preprocessing is enabled
        except ImportError:
            logger.warning("opencv-python-headless not installed. Skipping OCR preprocessing. "
                           "Run: pip install opencv-python-headless")
            return image

        logger.debug("Running OpenCV OCR preprocessing pipeline...")

        # Convert PIL → NumPy array for OpenCV
        cv_img = np.array(image.convert("RGB"))

        # ── Stage 1: Grayscale conversion ────────────────────────────────────
        gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
        logger.debug("  [✓] Grayscale conversion")

        # ── Stage 2: Denoising ────────────────────────────────────────────────
        # fastNlMeansDenoising works on 8-bit grayscale images.
        # h=10: filter strength (lower = keep more detail, higher = more smoothing)
        denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
        logger.debug("  [✓] Non-local means denoising")

        # ── Stage 3: Deskew ───────────────────────────────────────────────────
        deskewed = self._deskew(denoised)
        logger.debug("  [✓] Deskew")

        # ── Stage 4: Adaptive Thresholding ────────────────────────────────────
        # Gaussian adaptive threshold handles uneven lighting across the page.
        # blockSize=11, C=2 are robust defaults for most document types.
        binary = cv2.adaptiveThreshold(
            deskewed, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11, C=2
        )
        logger.debug("  [✓] Adaptive thresholding")

        # ── Stage 5: Sharpening ───────────────────────────────────────────────
        # Unsharp-mask kernel emphasises high-frequency edges (character strokes).
        kernel = np.array([[0, -1, 0],
                            [-1, 5, -1],
                            [0, -1, 0]], dtype=np.float32)
        sharpened = cv2.filter2D(binary, -1, kernel)
        logger.debug("  [✓] Sharpening kernel applied")

        # Convert back to PIL (mode 'L' = 8-bit grayscale)
        result = Image.fromarray(sharpened)
        logger.debug("OpenCV preprocessing pipeline completed successfully.")
        return result

    def _deskew(self, gray: np.ndarray) -> np.ndarray:
        """
        Detect and correct document skew using the image moments approach.

        Finds the minimum bounding box of all dark pixels and rotates the
        image to align the text to horizontal. Skips correction if the
        detected angle is less than 0.5° (avoids unnecessary resampling).

        Args:
            gray: Grayscale NumPy array.

        Returns:
            Deskewed grayscale NumPy array.
        """
        try:
            import cv2
            # Threshold to find dark pixel locations (text pixels)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            coords = np.column_stack(np.where(thresh > 0))

            if len(coords) < 5:
                # Not enough dark pixels to determine angle
                return gray

            # minAreaRect returns ((cx, cy), (w, h), angle)
            angle = cv2.minAreaRect(coords)[-1]

            # OpenCV returns angles in [-90, 0); convert to standard rotation
            if angle < -45:
                angle = 90 + angle

            # Skip rotation for nearly-straight images (< 0.5° deviation)
            if abs(angle) < 0.5:
                return gray

            (h, w) = gray.shape
            center = (w // 2, h // 2)
            # Build rotation matrix and apply affine transform
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                gray, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE  # fill edges with border colour
            )
            logger.debug(f"  [✓] Deskew angle corrected: {angle:.2f}°")
            return rotated

        except Exception as e:
            logger.warning(f"Deskew failed (non-critical): {e}")
            return gray


# ══════════════════════════════════════════════════════════════════════════════
# OCR Engine (Tesseract + EasyOCR fallback, now with OpenCV preprocessing)
# ══════════════════════════════════════════════════════════════════════════════

class OCREngine:
    """
    Layout-aware OCR engine with two stages:
      1. Tesseract (primary) — fast, accurate for clean scans
      2. EasyOCR (fallback) — deep-learning based, handles degraded scans

    v2.0 Enhancement: Both stages now pre-process the input image through the
    OpenCV ImagePreprocessor pipeline when ENABLE_OCR_PREPROCESSING=true.
    """

    def __init__(self):
        self._easyocr_reader = None
        self._preprocessor = ImagePreprocessor()

    def _get_easyocr_reader(self):
        """Lazy initialization of EasyOCR reader to save startup memory/time."""
        if self._easyocr_reader is None:
            import easyocr
            logger.info("Initializing EasyOCR reader (English)...")
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False)
        return self._easyocr_reader

    def perform_ocr(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Runs OCR on a given image file.

        If ENABLE_OCR_PREPROCESSING=true (default), runs the OpenCV enhancement
        pipeline first to improve accuracy on scanned/noisy inputs.

        Prioritises either EasyOCR or Tesseract based on Settings.prefer_easyocr,
        with graceful fallback to the other engine to prevent deployment crashes.

        Returns a list of word/block dictionaries with:
          - 'text':       extracted text string
          - 'bbox':       {'x0', 'y0', 'x1', 'y1'} normalized to 0-1000 grid
          - 'confidence': float in [0, 1]
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at: {image_path}")

        # Load the original image
        original_image = Image.open(image_path)
        width, height = original_image.size

        # ── v2.0: Apply OpenCV preprocessing if enabled ───────────────────────
        if settings.enable_ocr_preprocessing:
            logger.info(f"Applying OpenCV preprocessing to: {image_path}")
            ocr_image = self._preprocessor.preprocess(original_image)
        else:
            ocr_image = original_image

        # Determine OCR order based on preference
        engines = ["easyocr", "tesseract"] if settings.prefer_easyocr else ["tesseract", "easyocr"]
        errors = []

        for engine in engines:
            try:
                if engine == "tesseract":
                    logger.info(f"Running Tesseract OCR on: {image_path}")
                    # Verify if pytesseract is usable (raises exception if binary not found)
                    try:
                        pytesseract.get_tesseract_version()
                    except Exception as e:
                        raise RuntimeError("Tesseract binary is not installed or not in system PATH.") from e

                    ocr_data = pytesseract.image_to_data(ocr_image, output_type=pytesseract.Output.DICT)

                    blocks = []
                    current_block = []
                    x0, y0, x1, y1 = float('inf'), float('inf'), 0, 0

                    # Group word-level Tesseract output into line/paragraph blocks
                    for i in range(len(ocr_data["text"])):
                        text = ocr_data["text"][i].strip()
                        conf = ocr_data["conf"][i]

                        # Skip empty tokens and low-confidence detections
                        if not text or conf < 10:
                            continue

                        left = ocr_data["left"][i]
                        top  = ocr_data["top"][i]
                        w    = ocr_data["width"][i]
                        h    = ocr_data["height"][i]

                        # Normalize pixel coordinates to 0-1000 relative grid
                        rx0 = (left / width) * 1000
                        ry0 = (top  / height) * 1000
                        rx1 = ((left + w) / width) * 1000
                        ry1 = ((top  + h) / height) * 1000

                        if not current_block:
                            current_block = [text]
                            x0, y0, x1, y1 = rx0, ry0, rx1, ry1
                        else:
                            # Group words on the same line (within 15 units vertically)
                            if abs(ry0 - y0) < 15:
                                current_block.append(text)
                                x0 = min(x0, rx0); y0 = min(y0, ry0)
                                x1 = max(x1, rx1); y1 = max(y1, ry1)
                            else:
                                # Flush current paragraph block
                                blocks.append({
                                    "text":       " ".join(current_block),
                                    "bbox":       {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                                    "confidence": conf / 100.0
                                })
                                current_block = [text]
                                x0, y0, x1, y1 = rx0, ry0, rx1, ry1

                    # Flush trailing block
                    if current_block:
                        blocks.append({
                            "text":       " ".join(current_block),
                            "bbox":       {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                            "confidence": 1.0
                        })

                    if blocks:
                        logger.info(f"Tesseract OCR extracted {len(blocks)} layout blocks.")
                        return blocks
                    else:
                        raise ValueError("Tesseract returned empty text.")

                elif engine == "easyocr":
                    logger.info(f"Running EasyOCR on: {image_path}")
                    reader = self._get_easyocr_reader()

                    # EasyOCR accepts both file paths and NumPy arrays.
                    # Pass the preprocessed image as a numpy array for consistency.
                    import numpy as _np
                    ocr_input = _np.array(ocr_image)
                    results = reader.readtext(ocr_input)

                    blocks = []
                    for bbox_coords, text, conf in results:
                        if not text.strip():
                            continue

                        # EasyOCR coords: [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
                        lx0, ly0 = bbox_coords[0]
                        lx1, ly1 = bbox_coords[2]

                        rx0 = (lx0 / width) * 1000
                        ry0 = (ly0 / height) * 1000
                        rx1 = (lx1 / width) * 1000
                        ry1 = (ly1 / height) * 1000

                        blocks.append({
                            "text":       text.strip(),
                            "bbox":       {"x0": rx0, "y0": ry0, "x1": rx1, "y1": ry1},
                            "confidence": float(conf)
                        })

                    logger.info(f"EasyOCR extracted {len(blocks)} layout blocks.")
                    return blocks

            except Exception as e:
                logger.warning(f"OCR Engine '{engine}' failed: {e}")
                errors.append(f"{engine}: {e}")

        # If we reach here, all engines in our preference list failed
        raise RuntimeError(f"All OCR engines failed for {image_path}. Errors: {', '.join(errors)}")

