import fitz
import pytesseract
from PIL import Image
import io
from typing import List
from .pdf_parser import TextBlock

class OCRFallback:
    """Perform OCR on pages with low text yield."""
    
    def __init__(self, pdf_path: str, min_text_threshold: int = 50):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.min_text_threshold = min_text_threshold
    
    def needs_ocr(self, page_num: int) -> bool:
        """Check if page needs OCR based on text content."""
        page = self.doc[page_num]
        text = page.get_text()
        return len(text.strip()) < self.min_text_threshold
    
    def ocr_page(self, page_num: int) -> List[TextBlock]:
        """Perform OCR on a single page."""
        page = self.doc[page_num]
        
        # Render page to image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        # Perform OCR with bounding box data
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        # Group words into blocks
        blocks = []
        current_block = []
        current_bbox = None
        
        for i, text in enumerate(ocr_data["text"]):
            if text.strip():
                x, y, w, h = (
                    ocr_data["left"][i],
                    ocr_data["top"][i],
                    ocr_data["width"][i],
                    ocr_data["height"][i]
                )
                
                # Scale back from 2x zoom
                x, y, w, h = x / 2, y / 2, w / 2, h / 2
                
                if not current_block:
                    current_block = [text]
                    current_bbox = [x, y, x + w, y + h]
                else:
                    # Check if word is close enough to current block
                    if abs(y - current_bbox[1]) < 20:  # Same line
                        current_block.append(text)
                        current_bbox[2] = max(current_bbox[2], x + w)
                        current_bbox[3] = max(current_bbox[3], y + h)
                    else:
                        # Save current block and start new one
                        if current_block:
                            blocks.append(TextBlock(
                                text=" ".join(current_block),
                                page_number=page_num + 1,
                                bbox={
                                    "x0": current_bbox[0],
                                    "y0": current_bbox[1],
                                    "x1": current_bbox[2],
                                    "y1": current_bbox[3]
                                },
                                block_type="paragraph",
                                font_size=12,
                                font_name="ocr"
                            ))
                        current_block = [text]
                        current_bbox = [x, y, x + w, y + h]
        
        # Add last block
        if current_block:
            blocks.append(TextBlock(
                text=" ".join(current_block),
                page_number=page_num + 1,
                bbox={
                    "x0": current_bbox[0],
                    "y0": current_bbox[1],
                    "x1": current_bbox[2],
                    "y1": current_bbox[3]
                },
                block_type="paragraph",
                font_size=12,
                font_name="ocr"
            ))
        
        return blocks
    
    def close(self):
        """Close the PDF document."""
        self.doc.close()