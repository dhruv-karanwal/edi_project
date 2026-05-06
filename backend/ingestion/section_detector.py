from typing import List, Optional
from .pdf_parser import TextBlock

class SectionDetector:
    """Detect section titles and assign blocks to sections."""
    
    def __init__(self, heading_font_threshold: float = 14.0):
        self.heading_font_threshold = heading_font_threshold
    
    def detect_sections(self, text_blocks: List[TextBlock]) -> List[TextBlock]:
        """Assign section titles to text blocks."""
        current_section = None
        
        for block in text_blocks:
            # Check if this block is a heading
            if self._is_heading(block):
                current_section = block.text.strip()
            else:
                # Assign current section to this block
                block.metadata['section_title'] = current_section
        
        return text_blocks
    
    def _is_heading(self, block: TextBlock) -> bool:
        """Determine if a text block is a heading."""
        # Heuristics for heading detection:
        # 1. Font size above threshold
        # 2. Short text (< 100 chars)
        # 3. Not ending with period
        
        is_large_font = block.font_size >= self.heading_font_threshold
        is_short = len(block.text) < 100
        no_period = not block.text.strip().endswith('.')
        
        return is_large_font and is_short and no_period
    
    def get_section_title(self, block: TextBlock) -> Optional[str]:
        """Get the section title for a block."""
        return block.metadata.get('section_title')