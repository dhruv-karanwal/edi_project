import fitz  # PyMuPDF
from typing import List, Dict, Any
from dataclasses import dataclass, field

@dataclass
class TextBlock:
    """Represents a text block extracted from PDF."""
    text: str
    page_number: int
    bbox: Dict[str, float]  # {x0, y0, x1, y1}
    block_type: str  # paragraph, heading, etc.
    font_size: float
    font_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class PDFParser:
    """Extract text blocks with positioning from PDF using PyMuPDF."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.page_count = len(self.doc)
    
    def extract_text_blocks(self) -> List[TextBlock]:
        """Extract all text blocks with metadata."""
        blocks = []
        
        for page_num in range(self.page_count):
            page = self.doc[page_num]
            text_dict = page.get_text("dict")
            
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    text = self._extract_block_text(block)
                    if text.strip():
                        # Detect font info from first line
                        font_info = self._get_font_info(block)
                        
                        blocks.append(TextBlock(
                            text=text,
                            page_number=page_num + 1,
                            bbox={
                                "x0": block["bbox"][0],
                                "y0": block["bbox"][1],
                                "x1": block["bbox"][2],
                                "y1": block["bbox"][3]
                            },
                            block_type=self._classify_block_type(font_info["size"]),
                            font_size=font_info["size"],
                            font_name=font_info["name"]
                        ))
        
        return blocks
    
    def _extract_block_text(self, block: Dict) -> str:
        """Extract text from a block dictionary."""
        text_parts = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text_parts.append(span.get("text", ""))
        return " ".join(text_parts)
    
    def _get_font_info(self, block: Dict) -> Dict[str, Any]:
        """Get font information from first span."""
        if block.get("lines"):
            first_line = block["lines"][0]
            if first_line.get("spans"):
                first_span = first_line["spans"][0]
                return {
                    "size": first_span.get("size", 12),
                    "name": first_span.get("font", "unknown")
                }
        return {"size": 12, "name": "unknown"}
    
    def _classify_block_type(self, font_size: float) -> str:
        """Classify block as heading or paragraph based on font size."""
        if font_size > 14:
            return "heading"
        return "paragraph"
    
    def get_page_dimensions(self, page_num: int) -> Dict[str, float]:
        """Get page width and height."""
        page = self.doc[page_num]
        rect = page.rect
        return {"width": rect.width, "height": rect.height}
    
    def close(self):
        """Close the PDF document."""
        self.doc.close()