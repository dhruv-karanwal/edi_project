from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny
from typing import List, Dict, Any
from uuid import UUID
from config import get_settings
from embeddings.embedder import Embedder

settings = get_settings()

class VectorSearch:
    """Handle vector similarity search using Qdrant."""
    
    def __init__(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )
        self.embedder = Embedder()
        self.collection_name = "chunks"
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedder.get_dimension(),
                    distance=Distance.COSINE
                )
            )
            print(f"✓ Created Qdrant collection: {self.collection_name}")
    
    def index_chunks(self, chunks: List[Dict[str, Any]]):
        """Index a batch of chunks."""
        if not chunks:
            return
        
        # Prepare texts for embedding
        texts = [chunk['embedding_text'] for chunk in chunks]
        
        # Get embeddings
        print(f"Embedding {len(texts)} chunks...")
        embeddings = self.embedder.embed_batch(texts)
        
        # Prepare points for Qdrant
        points = []
        for i, chunk in enumerate(chunks):
            points.append(
                PointStruct(
                    id=chunk['chunk_id'],
                    vector=embeddings[i],
                    payload={
                        'document_id': chunk['document_id'],
                        'chunk_type': chunk['chunk_type'],
                        'page_number': chunk['page_number'],
                        'section_title': chunk.get('section_title'),
                        'content': chunk['content'][:1000],  # Truncate for storage
                        'caption': chunk.get('caption'),
                        'image_path': chunk.get('image_path'),
                        'chunk_index': chunk.get('chunk_index', 0)
                    }
                )
            )
        
        # Upload to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print(f"✓ Indexed {len(points)} chunks in Qdrant")
    
    def search(
        self,
        query: str,
        document_id: str = None,
        top_k: int = None,
        chunk_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks."""
        if top_k is None:
            top_k = settings.top_k_vector
        
        # Embed query
        query_vector = self.embedder.embed_text(query)
        
        # Build filter
        filter_conditions = []
        if document_id:
            filter_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id)
                )
            )
        
        if chunk_types:
            filter_conditions.append(
                FieldCondition(
                    key="chunk_type",
                    match=MatchAny(any=chunk_types)
                )
            )
        
        search_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=top_k
        )
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                'chunk_id': result.id,
                'score': result.score,
                'document_id': result.payload['document_id'],
                'chunk_type': result.payload['chunk_type'],
                'page_number': result.payload['page_number'],
                'section_title': result.payload.get('section_title'),
                'content': result.payload['content'],
                'caption': result.payload.get('caption'),
                'image_path': result.payload.get('image_path')
            })
        
        return formatted_results
    
    def delete_document_chunks(self, document_id: str):
        """Delete all chunks for a document."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id)
                    )
                ]
            )
        )