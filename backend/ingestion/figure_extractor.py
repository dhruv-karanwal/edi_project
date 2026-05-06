import fitz

from typing import List, Dict, Any
from dataclasses import dataclass, field
from file_storage.file_store import FileStore
@dataclass
class Figure:
    """Represents an extracted figure."""
    page_number: int
    bbox: Dict[str, float]
    image_path: str
    fig_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

class FigureExtractor:
    """Extract embedded images from PDF."""
    
    def __init__(self, pdf_path: str, document_id: str):
        self.pdf_path = pdf_path
        self.document_id = document_id
        self.doc = fitz.open(pdf_path)
        self.file_store = FileStore()
    
    def extract_figures(self) -> List[Figure]:
        """Extract all figures from PDF."""
        figures = []
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            image_list = page.get_images(full=True)
            
            for fig_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = self.doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Get image position on page
                    bbox = self._get_image_bbox(page, xref)
                    
                    # Save image
                    image_path = self.file_store.save_figure(
                        self.document_id,
                        page_num + 1,
                        fig_index,
                        image_bytes
                    )
                    
                    figures.append(Figure(
                        page_number=page_num + 1,
                        bbox=bbox,
                        image_path=image_path,
                        fig_index=fig_index
                    ))
                except Exception as e:
                    print(f"Failed to extract image on page {page_num + 1}: {e}")
                    continue
        
        return figures
    
    def _get_image_bbox(self, page, xref: int) -> Dict[str, float]:
        """Get bounding box of image on page."""
        # Get all image placements
        for item in page.get_images(full=True):
            if item[0] == xref:
                # Get image rectangle
                img_rects = page.get_image_rects(item[0])
                if img_rects:
                    rect = img_rects[0]
                    return {
                        "x0": rect.x0,
                        "y0": rect.y0,
                        "x1": rect.x1,
                        "y1": rect.y1
                    }
        
        # Default bbox if not found
        return {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
    
    def close(self):
        """Close the PDF document."""
        self.doc.close()