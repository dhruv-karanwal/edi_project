import os
import pytesseract
from PIL import Image
from typing import List, Dict, Any
from utils.logger import logger

class OCREngine:
    """Performs layout-aware OCR using Tesseract with an EasyOCR fallback."""
    
    def __init__(self):
        self._easyocr_reader = None

    def _get_easyocr_reader(self):
        """Lazy initialization of EasyOCR reader to save startup memory/time."""
        if self._easyocr_reader is None:
            import easyocr
            logger.info("Initializing EasyOCR reader (English)...")
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False)
        return self._easyocr_reader

    def perform_ocr(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Runs OCR on a given image. 
        Returns a list of word/block dictionaries with 'text', 'bbox' (x0, y0, x1, y1), and 'confidence'.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at: {image_path}")

        image = Image.open(image_path)
        width, height = image.size

        # 1. Try Tesseract OCR first
        try:
            logger.info(f"Running Tesseract OCR on: {image_path}")
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            blocks = []
            current_block = []
            x0, y0, x1, y1 = float('inf'), float('inf'), 0, 0
            
            # Tesseract groups by block_num / line_num. Let's group words into clean layout paragraphs.
            for i in range(len(ocr_data["text"])):
                text = ocr_data["text"][i].strip()
                conf = ocr_data["conf"][i]
                
                # Ignore whitespace and confidence marker -1 (denotes block boundaries)
                if not text or conf < 10:
                    continue
                
                left = ocr_data["left"][i]
                top = ocr_data["top"][i]
                w = ocr_data["width"][i]
                h = ocr_data["height"][i]
                
                # Normalize relative coordinates to a grid of 0-1000 for standard display sizing
                rx0 = (left / width) * 1000
                ry0 = (top / height) * 1000
                rx1 = ((left + w) / width) * 1000
                ry1 = ((top + h) / height) * 1000

                # Group words into blocks if they belong to the same block/line
                if not current_block:
                    current_block = [text]
                    x0, y0, x1, y1 = rx0, ry0, rx1, ry1
                else:
                    # If same line/block or relatively close, group them
                    if abs(ry0 - y0) < 15:  # pixels/percent scale diff
                        current_block.append(text)
                        x0 = min(x0, rx0)
                        y0 = min(y0, ry0)
                        x1 = max(x1, rx1)
                        y1 = max(y1, ry1)
                    else:
                        # Yield the previous paragraph block
                        blocks.append({
                            "text": " ".join(current_block),
                            "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                            "confidence": conf / 100.0
                        })
                        current_block = [text]
                        x0, y0, x1, y1 = rx0, ry0, rx1, ry1

            # Append trailing block
            if current_block:
                blocks.append({
                    "text": " ".join(current_block),
                    "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                    "confidence": 1.0
                })
            
            # If tesseract returned text, return it
            if blocks:
                logger.info(f"Tesseract OCR extracted {len(blocks)} layout blocks.")
                return blocks
                
        except Exception as e:
            logger.warning(f"Tesseract OCR failed or is not installed. Falling back to EasyOCR. Error: {e}")

        # 2. Fallback to EasyOCR
        try:
            logger.info(f"Running EasyOCR fallback on: {image_path}")
            reader = self._get_easyocr_reader()
            results = reader.readtext(image_path)
            
            blocks = []
            for bbox_coords, text, conf in results:
                if not text.strip():
                    continue
                
                # EasyOCR returns coordinates in format: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                lx0, ly0 = bbox_coords[0]
                lx1, ly1 = bbox_coords[2]
                
                # Normalize relative coordinates to 0-1000 scale
                rx0 = (lx0 / width) * 1000
                ry0 = (ly0 / height) * 1000
                rx1 = (lx1 / width) * 1000
                ry1 = (ly1 / height) * 1000
                
                blocks.append({
                    "text": text.strip(),
                    "bbox": {"x0": rx0, "y0": ry0, "x1": rx1, "y1": ry1},
                    "confidence": float(conf)
                })
                
            logger.info(f"EasyOCR fallback completed. Extracted {len(blocks)} layout blocks.")
            return blocks
            
        except Exception as ocr_err:
            logger.error(f"EasyOCR fallback failed as well: {ocr_err}")
            raise RuntimeError(f"All OCR engines failed for {image_path}: {ocr_err}") from ocr_err
