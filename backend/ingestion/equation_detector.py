import re
from typing import List
from dataclasses import dataclass, field
from .pdf_parser import TextBlock
from typing import Dict, Any

@dataclass
class Equation:
    """Represents a detected equation."""
    content: str
    page_number: int
    bbox: Dict[str, float]
    equation_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

class EquationDetector:
    """Detect equations in text blocks using heuristics."""
    
    # Patterns that indicate equations
    EQUATION_PATTERNS = [
        r'\$[^\$]+\$',  # LaTeX inline math
        r'\$\$[^\$]+\$\$',  # LaTeX display math
        r'\\begin\{equation\}.*?\\end\{equation\}',  # LaTeX equation environment
        r'\\begin\{align\}.*?\\end\{align\}',  # LaTeX align environment
        r'\([0-9]+\)\s*$',  # Equation numbers like (1) at end of line
        r'[a-zA-Z]\s*=\s*[^=]+[+\-*/^]',  # Simple equations like y = mx + b
    ]
    
    def __init__(self):
        self.patterns = [re.compile(p, re.DOTALL) for p in self.EQUATION_PATTERNS]
    
    def detect_equations(self, text_blocks: List[TextBlock]) -> List[Equation]:
        """Detect equations from text blocks."""
        equations = []
        equation_index = 0
        
        for block in text_blocks:
            # Check if block contains equation patterns
            for pattern in self.patterns:
                matches = pattern.findall(block.text)
                for match in matches:
                    equations.append(Equation(
                        content=match,
                        page_number=block.page_number,
                        bbox=block.bbox,
                        equation_index=equation_index
                    ))
                    equation_index += 1
            
            # Also detect lines with heavy mathematical symbols
            if self._is_equation_like(block.text):
                equations.append(Equation(
                    content=block.text,
                    page_number=block.page_number,
                    bbox=block.bbox,
                    equation_index=equation_index
                ))
                equation_index += 1
        
        return equations
    
    def _is_equation_like(self, text: str) -> bool:
        """Check if text looks like an equation based on symbol density."""
        math_symbols = r'[=+\-*/^∫∑∏√±≈≠≤≥∈∉∀∃αβγδεθλμπσφψω]'
        symbol_count = len(re.findall(math_symbols, text))
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return False
        
        # If more than 20% mathematical symbols, likely an equation
        return (symbol_count / total_chars) > 0.2