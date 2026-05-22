import os
import fitz  # PyMuPDF
from PIL import Image
from typing import List, Dict, Any, Tuple
from config import get_settings
from utils.logger import logger
from ocr.ocr_engine import OCREngine

settings = get_settings()

class PDFService:
    """Natively parses PDF layouts, renders page images, and crops grounded evidence regions."""
    
    def __init__(self):
        self.ocr_engine = OCREngine()

    def render_pages(self, pdf_path: str) -> List[str]:
        """
        Renders each page of a PDF as a high-res PNG image.
        Uses PyMuPDF's built-in rasterizer (extremely fast, zero external dependencies!).
        Returns list of absolute image file paths.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found at: {pdf_path}")

        doc = fitz.open(pdf_path)
        page_paths = []
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        logger.info(f"Rendering {len(doc)} pages for document: {base_name}")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Zoom matrix for higher quality rendering (2x)
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            page_filename = f"{base_name}_page_{page_num + 1}.png"
            page_path = os.path.join(settings.pages_dir, page_filename)
            
            pix.save(page_path)
            page_paths.append(page_path)
            
        doc.close()
        logger.info(f"Successfully rendered {len(page_paths)} pages.")
        return page_paths

    def extract_layout(self, pdf_path: str, page_images: List[str]) -> List[Dict[str, Any]]:
        """
        Parses text and layout.
        Uses native PyMuPDF structure first. For pages with low text density, runs layout-aware OCR.
        Returns a list of structured text chunks with coordinates.
        """
        doc = fitz.open(pdf_path)
        chunks = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_width = page.rect.width
            page_height = page.rect.height
            page_image_path = page_images[page_num]
            
            # 1. Native PyMuPDF text block extraction
            blocks = page.get_text("blocks")
            
            # Simple heuristic: if selectable text is less than 150 characters, assume scanned PDF page and run OCR
            raw_text = page.get_text().strip()
            
            if len(raw_text) < 150:
                logger.info(f"Low native text yield on page {page_num + 1} ({len(raw_text)} chars). Running OCR pipeline...")
                ocr_blocks = self.ocr_engine.perform_ocr(page_image_path)
                
                for idx, ob in enumerate(ocr_blocks):
                    chunks.append({
                        "chunk_type": "text",
                        "content": ob["text"],
                        "page_number": page_num + 1,
                        "section_title": "Scanned Document Content",
                        "caption": None,
                        "bbox": ob["bbox"],  # coordinates are already 0-1000 normalized
                        "image_path": page_image_path
                    })
            else:
                logger.info(f"Page {page_num + 1} contains native text. Parsing layout blocks...")
                
                # Check for visual elements (drawings, images)
                # Group native PyMuPDF text blocks
                for idx, block in enumerate(blocks):
                    # block format: (x0, y0, x1, y1, "text", block_no, block_type)
                    bx0, by0, bx1, by1, btext, bnum, btype = block
                    btext = btext.strip()
                    if not btext:
                        continue
                    
                    # Normalize absolute PDF coordinates to a 0-1000 relative grid
                    rx0 = (bx0 / page_width) * 1000
                    ry0 = (by0 / page_height) * 1000
                    rx1 = (bx1 / page_width) * 1000
                    ry1 = (by1 / page_height) * 1000
                    
                    # Determine chunk type by content checks
                    chunk_type = "text"
                    section_title = None
                    
                    # Simple heuristics for structural metadata
                    lower_text = btext.lower()
                    if len(btext) < 100 and any(kw in lower_text for kw in ["figure ", "fig. ", "fig "]):
                        chunk_type = "caption"
                    elif len(btext) < 100 and any(kw in lower_text for kw in ["table ", "tbl "]):
                        chunk_type = "caption"
                    elif len(btext) < 150 and (btext.isupper() or btext.istitle() or btext[0].isdigit()):
                        # Looks like a section header
                        section_title = btext.split('\n')[0]
                    
                    chunks.append({
                        "chunk_type": chunk_type,
                        "content": btext,
                        "page_number": page_num + 1,
                        "section_title": section_title,
                        "caption": btext if chunk_type == "caption" else None,
                        "bbox": {"x0": rx0, "y0": ry0, "x1": rx1, "y1": ry1},
                        "image_path": page_image_path
                    })
                    
                # Identify and extract tables / figures
                # PyMuPDF has built-in table finder
                tabs = page.find_tables()
                for t_idx, tab in enumerate(tabs):
                    tx0, ty0, tx1, ty1 = tab.bbox
                    trx0 = (tx0 / page_width) * 1000
                    try0 = (ty0 / page_height) * 1000
                    trx1 = (tx1 / page_width) * 1000
                    try1 = (ty1 / page_height) * 1000
                    
                    # Generate a tabular text view
                    table_data = tab.extract()
                    table_str = "\n".join([" | ".join([cell or "" for cell in row]) for row in table_data])
                    
                    chunks.append({
                        "chunk_type": "table",
                        "content": f"Table structure data:\n{table_str}",
                        "page_number": page_num + 1,
                        "section_title": "Tabular Data Extraction",
                        "caption": None,
                        "bbox": {"x0": trx0, "y0": try0, "x1": trx1, "y1": try1},
                        "image_path": page_image_path
                    })
                    
                # Identify raw PDF image drawings to extract figures
                drawings = page.get_drawings()
                img_list = page.get_images()
                
                # If there are image instances, lets index them
                for i_idx, img in enumerate(img_list):
                    xref = img[0]
                    rects = page.get_image_rects(xref)
                    for rect in rects:
                        ix0, iy0, ix1, iy1 = rect
                        irx0 = (ix0 / page_width) * 1000
                        iry0 = (iy0 / page_height) * 1000
                        irx1 = (ix1 / page_width) * 1000
                        iry1 = (iy1 / page_height) * 1000
                        
                        chunks.append({
                            "chunk_type": "figure",
                            "content": f"Visual component detected on page {page_num + 1} at region [{rect}]",
                            "page_number": page_num + 1,
                            "section_title": "Visual Figure Extraction",
                            "caption": None,
                            "bbox": {"x0": irx0, "y0": iry0, "x1": irx1, "y1": iry1},
                            "image_path": page_image_path
                        })

        doc.close()
        logger.info(f"Extracted {len(chunks)} combined layout chunks.")
        return chunks

    def crop_region(self, page_image_path: str, bbox: Dict[str, float], output_path: str) -> bool:
        """
        Crops a region from the full page PNG using the normalized bounding box.
        Saves the cropped region to output_path.
        """
        try:
            if not os.path.exists(page_image_path):
                return False
            
            image = Image.open(page_image_path)
            width, height = image.size
            
            # Map normalized 0-1000 grid coordinates back to actual pixel dimensions
            px0 = (bbox["x0"] / 1000) * width
            py0 = (bbox["y0"] / 1000) * height
            px1 = (bbox["x1"] / 1000) * width
            py1 = (bbox["y1"] / 1000) * height
            
            # Add padding to prevent tight crops
            padding = 10
            px0 = max(0, px0 - padding)
            py0 = max(0, py0 - padding)
            px1 = min(width, px1 + padding)
            py1 = min(height, py1 + padding)
            
            # Perform crop if region width/height is valid
            if (px1 - px0) > 5 and (py1 - py0) > 5:
                cropped = image.crop((px0, py0, px1, py1))
                cropped.save(output_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to crop region: {e}")
            return False
