from typing import List, Dict, Set
from graph.graph_builder import GraphBuilder
from config import get_settings

settings = get_settings()

class GraphSearch:
    """Search using knowledge graph traversal."""
    
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.graph_builder = GraphBuilder.load_graph(document_id)
    
    def get_graph_neighbors(
        self,
        seed_chunk_ids: List[str],
        max_depth: int = 2,
        top_k: int = None
    ) -> List[str]:
        """Get neighboring chunks from graph traversal."""
        if top_k is None:
            top_k = settings.top_k_graph
        
        all_neighbors = set()
        
        for chunk_id in seed_chunk_ids:
            neighbors = self.graph_builder.get_neighbors(chunk_id, max_depth)
            all_neighbors.update(neighbors)
        
        # Remove seed chunks from neighbors
        all_neighbors -= set(seed_chunk_ids)
        
        # Limit to top_k
        return list(all_neighbors)[:top_k]
    
    def get_related_figures(self, chunk_id: str) -> List[str]:
        """Get figures related to a chunk."""
        # Get chunks that this chunk refers to
        referred = self.graph_builder.get_related_by_type(chunk_id, 'refers_to')
        
        # Get chunks in proximity
        nearby = self.graph_builder.get_related_by_type(chunk_id, 'next_to')
        
        # Filter for figures only
        all_related = set(referred + nearby)
        
        # TODO: Filter by chunk type (need to query DB or store in graph)
        return list(all_related)
    
    def get_section_chunks(self, chunk_id: str) -> List[str]:
        """Get all chunks in the same section."""
        # Get section node
        node_id = f"chunk:{chunk_id}"
        graph = self.graph_builder.graph
        
        if node_id not in graph:
            return []
        
        # Find section this chunk belongs to
        section_node = None
        for neighbor in graph.neighbors(node_id):
            if neighbor.startswith('section:'):
                section_node = neighbor
                break
        
        if not section_node:
            return []
        
        # Get all chunks in this section
        section_chunks = []
        for node in graph.predecessors(section_node):
            if node.startswith('chunk:'):
                section_chunks.append(node.replace('chunk:', ''))
        
        return section_chunks
    
    def expand_with_captions(self, chunk_ids: List[str]) -> List[str]:
        """For figure/table chunks, add their captions."""
        expanded = set(chunk_ids)
        
        for chunk_id in chunk_ids:
            # Get caption if this is a figure/table
            captions = self.graph_builder.get_related_by_type(chunk_id, 'has_caption')
            expanded.update(captions)
            
            # If this is a caption, get what it describes
            describes = self.graph_builder.get_related_by_type(chunk_id, 'describes')
            expanded.update(describes)
        
        return list(expanded)