from typing import List, Dict
import re

class QueryClassifier:
    """Classify query intent to determine retrieval strategy."""
    
    # Keywords that indicate specific content types
    FIGURE_KEYWORDS = [
        'figure', 'fig', 'diagram', 'chart', 'plot', 'graph', 'image',
        'illustration', 'visualization', 'show', 'display'
    ]
    
    TABLE_KEYWORDS = [
        'table', 'data', 'results', 'comparison', 'statistics', 'values',
        'numbers', 'metrics', 'performance'
    ]
    
    EQUATION_KEYWORDS = [
        'equation', 'formula', 'mathematical', 'calculation', 'compute',
        'derive', 'proof', 'expression'
    ]
    
    def classify(self, query: str) -> Dict[str, any]:
        """Classify query and return preferred chunk types and strategy."""
        query_lower = query.lower()
        
        classification = {
            'query': query,
            'preferred_types': [],
            'requires_visual': False,
            'search_strategy': 'hybrid'
        }
        
        # Check for figure-related queries
        if any(keyword in query_lower for keyword in self.FIGURE_KEYWORDS):
            classification['preferred_types'].append('figure')
            classification['requires_visual'] = True
        
        # Check for table-related queries
        if any(keyword in query_lower for keyword in self.TABLE_KEYWORDS):
            classification['preferred_types'].append('table')
        
        # Check for equation-related queries
        if any(keyword in query_lower for keyword in self.EQUATION_KEYWORDS):
            classification['preferred_types'].append('equation')
        
        # If no specific type detected, include all
        if not classification['preferred_types']:
            classification['preferred_types'] = ['text', 'figure', 'table', 'equation']
        else:
            # Always include text for context
            if 'text' not in classification['preferred_types']:
                classification['preferred_types'].append('text')
        
        # Check for explicit figure/table references (e.g., "Figure 3", "Table 1")
        fig_ref = re.search(r'fig(?:ure)?\s*[:#\-]?\s*(\d+)', query_lower)
        image_ref = re.search(r'image\s*[:#\-]?\s*(\d+)', query_lower)
        table_ref = re.search(r'table\s*[:#\-]?\s*(\d+)', query_lower)
        
        if fig_ref or image_ref or table_ref:
            classification['search_strategy'] = 'reference_based'
            classification['requires_visual'] = True
            
            if fig_ref:
                classification['figure_number'] = fig_ref.group(1)
            elif image_ref:
                classification['figure_number'] = image_ref.group(1)
            if table_ref:
                classification['table_number'] = table_ref.group(1)
        
        return classification