import networkx as nx
from typing import List, Dict, Set, Optional
import pickle
from pathlib import Path
from chunking.chunker import NormalizedChunk
from file_storage.file_store import FileStore

class GraphBuilder:
    """Build and manage knowledge graph for a document."""
    
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.graph = nx.DiGraph()
        self.file_store = FileStore()
    
    def build_graph(self, chunks: List[NormalizedChunk]) -> nx.DiGraph:
        """Build complete knowledge graph from chunks."""
        
        # Add document node
        self.graph.add_node(
            f"doc:{self.document_id}",
            node_type='document',
            document_id=self.document_id
        )
        
        # Track sections for linking
        sections: Dict[str, str] = {}  # section_title -> node_id
        
        # Group chunks by page for proximity detection
        chunks_by_page: Dict[int, List[NormalizedChunk]] = {}
        for chunk in chunks:
            if chunk.page_number not in chunks_by_page:
                chunks_by_page[chunk.page_number] = []
            chunks_by_page[chunk.page_number].append(chunk)
        
        # Add all chunk nodes
        for chunk in chunks:
            node_id = f"chunk:{chunk.chunk_id}"
            
            # Add node with attributes
            self.graph.add_node(
                node_id,
                node_type=chunk.chunk_type,
                chunk_id=str(chunk.chunk_id),
                content=chunk.content[:500],  # Store truncated content
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                caption=chunk.caption,
                image_path=chunk.image_path,
                chunk_index=chunk.chunk_index
            )
            
            # Link to document
            self.graph.add_edge(node_id, f"doc:{self.document_id}", relation='belongs_to_doc')
            
            # Handle section nodes
            if chunk.section_title:
                section_node = f"section:{chunk.section_title}"
                if section_node not in sections:
                    # Create section node
                    self.graph.add_node(
                        section_node,
                        node_type='section',
                        title=chunk.section_title,
                        page_number=chunk.page_number
                    )
                    self.graph.add_edge(section_node, f"doc:{self.document_id}", relation='belongs_to_doc')
                    sections[chunk.section_title] = section_node
                
                # Link chunk to section
                self.graph.add_edge(node_id, section_node, relation='belongs_to_section')
        
        # Add caption relationships
        self._link_captions(chunks)
        
        # Add proximity relationships (same page)
        self._link_proximity(chunks_by_page)
        
        # Add reference relationships (explicit mentions)
        self._link_references(chunks)
        
        # Add sequential relationships
        self._link_sequential(chunks)
        
        return self.graph
    
    def _link_captions(self, chunks: List[NormalizedChunk]):
        """Link captions to their figures/tables."""
        caption_chunks = [c for c in chunks if c.chunk_type == 'caption']
        figure_chunks = [c for c in chunks if c.chunk_type == 'figure']
        table_chunks = [c for c in chunks if c.chunk_type == 'table']
        
        for caption in caption_chunks:
            caption_node = f"chunk:{caption.chunk_id}"
            
            # Find matching figure/table by proximity and page
            target_chunks = figure_chunks + table_chunks
            closest = None
            min_distance = float('inf')
            
            for target in target_chunks:
                if abs(target.page_number - caption.page_number) <= 1:
                    # Calculate vertical distance using bbox
                    if caption.bbox and target.bbox:
                        distance = abs(caption.bbox['y0'] - target.bbox['y0'])
                        if distance < min_distance:
                            min_distance = distance
                            closest = target
            
            if closest:
                target_node = f"chunk:{closest.chunk_id}"
                self.graph.add_edge(caption_node, target_node, relation='describes')
                self.graph.add_edge(target_node, caption_node, relation='has_caption')
    
    def _link_proximity(self, chunks_by_page: Dict[int, List[NormalizedChunk]]):
        """Link chunks that are close to each other on the same page."""
        for page_num, page_chunks in chunks_by_page.items():
            # Sort by vertical position
            sorted_chunks = sorted(
                page_chunks,
                key=lambda c: c.bbox['y0'] if c.bbox else 0
            )
            
            # Link adjacent chunks
            for i in range(len(sorted_chunks) - 1):
                curr = sorted_chunks[i]
                next_chunk = sorted_chunks[i + 1]
                
                curr_node = f"chunk:{curr.chunk_id}"
                next_node = f"chunk:{next_chunk.chunk_id}"
                
                # Add bidirectional proximity edge
                self.graph.add_edge(curr_node, next_node, relation='next_to')
                self.graph.add_edge(next_node, curr_node, relation='next_to')
    
    def _link_references(self, chunks: List[NormalizedChunk]):
        """Link text chunks that reference figures, tables, or equations."""
        import re
        
        text_chunks = [c for c in chunks if c.chunk_type == 'text']
        target_chunks = [c for c in chunks if c.chunk_type in ['figure', 'table', 'equation']]
        
        # Patterns for detecting references
        fig_pattern = re.compile(r'Fig(?:ure)?\.?\s*(\d+)', re.IGNORECASE)
        table_pattern = re.compile(r'Table\.?\s*(\d+)', re.IGNORECASE)
        eq_pattern = re.compile(r'Eq(?:uation)?\.?\s*(\d+)', re.IGNORECASE)
        
        for text_chunk in text_chunks:
            text_node = f"chunk:{text_chunk.chunk_id}"
            
            # Find figure references
            fig_matches = fig_pattern.findall(text_chunk.content)
            for fig_num in fig_matches:
                # Find corresponding figure
                for target in target_chunks:
                    if target.chunk_type == 'figure' and target.caption:
                        if f"Figure {fig_num}" in target.caption or f"Fig. {fig_num}" in target.caption:
                            target_node = f"chunk:{target.chunk_id}"
                            self.graph.add_edge(text_node, target_node, relation='refers_to')
            
            # Find table references
            table_matches = table_pattern.findall(text_chunk.content)
            for table_num in table_matches:
                for target in target_chunks:
                    if target.chunk_type == 'table' and target.caption:
                        if f"Table {table_num}" in target.caption:
                            target_node = f"chunk:{target.chunk_id}"
                            self.graph.add_edge(text_node, target_node, relation='refers_to')
    
    def _link_sequential(self, chunks: List[NormalizedChunk]):
        """Link chunks in document order."""
        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)
        
        for i in range(len(sorted_chunks) - 1):
            curr_node = f"chunk:{sorted_chunks[i].chunk_id}"
            next_node = f"chunk:{sorted_chunks[i + 1].chunk_id}"
            self.graph.add_edge(curr_node, next_node, relation='followed_by')
    
    def save_graph(self):
        """Serialize and save graph to disk."""
        graph_data = pickle.dumps(self.graph)
        self.file_store.save_graph(self.document_id, graph_data)
    
    @classmethod
    def load_graph(cls, document_id: str) -> 'GraphBuilder':
        """Load graph from disk."""
        builder = cls(document_id)
        file_store = FileStore()
        graph_data = file_store.load_graph(document_id)
        builder.graph = pickle.loads(graph_data)
        return builder
    
    def get_neighbors(self, chunk_id: str, max_depth: int = 2) -> List[str]:
        """Get neighboring chunks up to max_depth hops away."""
        node_id = f"chunk:{chunk_id}"
        
        if node_id not in self.graph:
            return []
        
        # BFS to find neighbors
        visited = set()
        queue = [(node_id, 0)]
        neighbors = []
        
        while queue:
            current, depth = queue.pop(0)
            
            if current in visited or depth > max_depth:
                continue
            
            visited.add(current)
            
            # Add to neighbors if it's a chunk node
            if current.startswith('chunk:') and current != node_id:
                neighbors.append(current.replace('chunk:', ''))
            
            # Add unvisited neighbors to queue
            if depth < max_depth:
                for neighbor in self.graph.neighbors(current):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
        
        return neighbors
    
    def get_related_by_type(self, chunk_id: str, relation_type: str) -> List[str]:
        """Get chunks connected by a specific relation type."""
        node_id = f"chunk:{chunk_id}"
        
        if node_id not in self.graph:
            return []
        
        related = []
        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph.get_edge_data(node_id, neighbor)
            if edge_data and edge_data.get('relation') == relation_type:
                if neighbor.startswith('chunk:'):
                    related.append(neighbor.replace('chunk:', ''))
        
        return related
    
    def get_graph_stats(self) -> Dict:
        """Get statistics about the graph."""
        node_types = {}
        for node, data in self.graph.nodes(data=True):
            node_type = data.get('node_type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        edge_types = {}
        for _, _, data in self.graph.edges(data=True):
            relation = data.get('relation', 'unknown')
            edge_types[relation] = edge_types.get(relation, 0) + 1
        
        return {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'node_types': node_types,
            'edge_types': edge_types
        }