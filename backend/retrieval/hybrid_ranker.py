from typing import List, Dict, Any
from sqlalchemy.orm import Session
from db.models import Chunk
from config import get_settings

settings = get_settings()

class HybridRanker:
    """Combine and re-rank results from vector and graph search."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def merge_and_rank(
        self,
        vector_results: List[Dict[str, Any]],
        graph_chunk_ids: List[str],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """Merge vector and graph results with hybrid scoring."""
        if top_k is None:
            top_k = settings.rerank_top_k
        
        # Create score map from vector results
        score_map = {}
        for result in vector_results:
            chunk_id = str(result['chunk_id'])
            score_map[chunk_id] = {
                'vector_score': result['score'],
                'graph_score': 0.0,
                'chunk_data': result
            }
        
        # Add graph results
        for chunk_id in graph_chunk_ids:
            if chunk_id not in score_map:
                # Fetch chunk from DB
                chunk = self.db.query(Chunk).filter(Chunk.id == chunk_id).first()
                if chunk:
                    score_map[chunk_id] = {
                        'vector_score': 0.0,
                        'graph_score': 0.5,  # Fixed score for graph-only results
                        'chunk_data': {
                            'chunk_id': str(chunk.id),
                            'document_id': str(chunk.document_id),
                            'chunk_type': chunk.chunk_type,
                            'page_number': chunk.page_number,
                            'section_title': chunk.section_title,
                            'content': chunk.content,
                            'caption': chunk.caption,
                            'image_path': chunk.image_path
                        }
                    }
            else:
                # Boost score for chunks found in both
                score_map[chunk_id]['graph_score'] = 0.3
        
        # Calculate hybrid scores
        # Formula: 0.7 * vector_score + 0.3 * graph_score
        ranked_results = []
        for chunk_id, scores in score_map.items():
            hybrid_score = 0.7 * scores['vector_score'] + 0.3 * scores['graph_score']
            
            result = scores['chunk_data'].copy()
            result['relevance_score'] = hybrid_score
            result['vector_score'] = scores['vector_score']
            result['graph_score'] = scores['graph_score']
            
            ranked_results.append(result)
        
        # Sort by hybrid score
        ranked_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return ranked_results[:top_k]
    
    def prioritize_by_type(
        self,
        results: List[Dict[str, Any]],
        preferred_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Boost results matching preferred chunk types."""
        boosted_results = []
        
        for result in results:
            if result['chunk_type'] in preferred_types:
                result['relevance_score'] *= 1.2  # 20% boost
            boosted_results.append(result)
        
        # Re-sort
        boosted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return boosted_results