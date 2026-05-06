import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from .pdf_parser import TextBlock
from .figure_extractor import Figure
from .table_extractor import Table

@dataclass
class Caption:
    """Represents a caption linked to a figure or table."""
    text: str
    page_number: int
    bbox: Dict[str, float]
    caption_type: str  # 'figure' or 'table'
    target_index: int  # Which figure/table this describes
    target_bbox: Optional[Dict[str, float]] = None

class CaptionLinker:
    """Link captions to figures and tables."""
    
    FIGURE_PATTERNS = [
        r'Fig(?:ure)?\.?\s*(\d+)',
        r'Figure\s+(\d+)',
        r'FIG\.?\s*(\d+)',
    ]
    
    TABLE_PATTERNS = [
        r'Table\.?\s*(\d+)',
        r'TABLE\.?\s*(\d+)',
    ]
    
    def __init__(self):
        self.fig_patterns = [re.compile(p, re.IGNORECASE) for p in self.FIGURE_PATTERNS]
        self.table_patterns = [re.compile(p, re.IGNORECASE) for p in self.TABLE_PATTERNS]
    
    def link_captions(
        self,
        text_blocks: List[TextBlock],
        figures: List[Figure],
        tables: List[Table]
    ) -> List[Caption]:
        """Find and link captions to figures and tables."""
        captions = []
        
        # Find figure captions
        for block in text_blocks:
            fig_match = self._match_figure_caption(block.text)
            if fig_match:
                fig_num = int(fig_match)
                # Find corresponding figure
                target_fig = self._find_nearest_figure(block, figures, fig_num)
                if target_fig:
                    captions.append(Caption(
                        text=block.text,
                        page_number=block.page_number,
                        bbox=block.bbox,
                        caption_type='figure',
                        target_index=fig_num,
                        target_bbox=target_fig.bbox
                    ))
            
            # Find table captions
            table_match = self._match_table_caption(block.text)
            if table_match:
                table_num = int(table_match)
                # Find corresponding table
                target_table = self._find_nearest_table(block, tables, table_num)
                if target_table:
                    captions.append(Caption(
                        text=block.text,
                        page_number=block.page_number,
                        bbox=block.bbox,
                        caption_type='table',
                        target_index=table_num,
                        target_bbox=target_table.bbox
                    ))
        
        return captions
    
    def _match_figure_caption(self, text: str) -> Optional[str]:
        """Check if text is a figure caption and extract figure number."""
        for pattern in self.fig_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None
    
    def _match_table_caption(self, text: str) -> Optional[str]:
        """Check if text is a table caption and extract table number."""
        for pattern in self.table_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None
    
    def _find_nearest_figure(
        self,
        caption_block: TextBlock,
        figures: List[Figure],
        fig_num: int
    ) -> Optional[Figure]:
        """Find the nearest figure on the same or adjacent page."""
        # Filter figures on same page or adjacent pages
        candidate_figures = [
            f for f in figures
            if abs(f.page_number - caption_block.page_number) <= 1
        ]
        
        if not candidate_figures:
            return None
        
        # Find closest by vertical distance
        min_dist = float('inf')
        closest = None
        
        for fig in candidate_figures:
            dist = abs(fig.bbox['y0'] - caption_block.bbox['y0'])
            if dist < min_dist:
                min_dist = dist
                closest = fig
        
        return closest
    
    def _find_nearest_table(
        self,
        caption_block: TextBlock,
        tables: List[Table],
        table_num: int
    ) -> Optional[Table]:
        """Find the nearest table on the same or adjacent page."""
        # Filter tables on same page or adjacent pages
        candidate_tables = [
            t for t in tables
            if abs(t.page_number - caption_block.page_number) <= 1
        ]
        
        if not candidate_tables:
            return None
        
        # Find closest by vertical distance
        min_dist = float('inf')
        closest = None
        
        for table in candidate_tables:
            dist = abs(table.bbox['y0'] - caption_block.bbox['y0'])
            if dist < min_dist:
                min_dist = dist
                closest = table
        
        return closest