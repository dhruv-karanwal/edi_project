from dataclasses import dataclass
from typing import Dict, Any, Optional
from uuid import UUID

@dataclass
class NormalizedChunk:
    """Normalized chunk representation for embedding and retrieval."""
    
    chunk_id: UUID
    document_id: UUID
    chunk_type: str  # text | figure | table | equation | caption
    content: str
    page_number: int
    section_title: Optional[str]
    caption: Optional[str]
    image_path: Optional[str]
    bbox: Optional[Dict[str, float]]
    metadata: Dict[str, Any]
    chunk_index: int
    
    def to_embedding_text(self) -> str:
        """Convert chunk to text suitable for embedding."""
        parts = []
        
        # Add section context
        if self.section_title:
            parts.append(f"Section: {self.section_title}")
        
        # Add type-specific prefix
        type_prefix = {
            'text': 'Text',
            'figure': 'Figure',
            'table': 'Table',
            'equation': 'Equation',
            'caption': 'Caption'
        }
        parts.append(f"{type_prefix.get(self.chunk_type, 'Content')}:")
        
        # Add caption if available
        if self.caption:
            parts.append(f"Caption: {self.caption}")
        
        # Add main content
        parts.append(self.content)
        
        # Add page reference
        parts.append(f"(Page {self.page_number})")
        
        return " ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'chunk_id': str(self.chunk_id),
            'document_id': str(self.document_id),
            'chunk_type': self.chunk_type,
            'content': self.content,
            'page_number': self.page_number,
            'section_title': self.section_title,
            'caption': self.caption,
            'image_path': self.image_path,
            'bbox': self.bbox,
            'metadata': self.metadata,
            'chunk_index': self.chunk_index
        }

class Chunker:
    """Utilities for working with chunks."""
    
    @staticmethod
    def from_db_chunk(db_chunk) -> NormalizedChunk:
        """Convert database Chunk model to NormalizedChunk."""
        return NormalizedChunk(
            chunk_id=db_chunk.id,
            document_id=db_chunk.document_id,
            chunk_type=db_chunk.chunk_type,
            content=db_chunk.content,
            page_number=db_chunk.page_number,
            section_title=db_chunk.section_title,
            caption=db_chunk.caption,
            image_path=db_chunk.image_path,
            bbox=db_chunk.bbox,
            metadata=db_chunk.extra_metadata or {},
            chunk_index=db_chunk.chunk_index or 0
        )
    
    @staticmethod
    def get_chunk_summary(chunk: NormalizedChunk, max_length: int = 200) -> str:
        """Get a short summary of chunk content."""
        content = chunk.content[:max_length]
        if len(chunk.content) > max_length:
            content += "..."
        return content