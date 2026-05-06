import pdfplumber
from typing import List, Dict, Any
from dataclasses import dataclass, field

@dataclass
class Table:
    """Represents an extracted table."""
    page_number: int
    bbox: Dict[str, float]
    rows: List[List[str]]
    table_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

class TableExtractor:
    """Extract tables from PDF using pdfplumber."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf = pdfplumber.open(pdf_path)
    
    def extract_tables(self) -> List[Table]:
        """Extract all tables from PDF."""
        tables = []
        
        for page_num, page in enumerate(self.pdf.pages):
            page_tables = page.find_tables()
            
            for table_index, table_obj in enumerate(page_tables):
                try:
                    # Extract table data
                    table_data = table_obj.extract()
                    
                    if table_data and len(table_data) > 1:  # At least header + 1 row
                        tables.append(Table(
                            page_number=page_num + 1,
                            bbox={
                                "x0": table_obj.bbox[0],
                                "y0": table_obj.bbox[1],
                                "x1": table_obj.bbox[2],
                                "y1": table_obj.bbox[3]
                            },
                            rows=table_data,
                            table_index=table_index
                        ))
                except Exception as e:
                    print(f"Failed to extract table on page {page_num + 1}: {e}")
                    continue
        
        return tables
    
    def close(self):
        """Close the PDF file."""
        self.pdf.close()