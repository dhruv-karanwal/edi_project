from typing import List
from sqlalchemy.orm import Session
from db.models import Document, Chunk
from file_storage.file_store import FileStore
from .pdf_parser import PDFParser, TextBlock
from .ocr_fallback import OCRFallback
from .figure_extractor import FigureExtractor
from .table_extractor import TableExtractor
from .equation_detector import EquationDetector
from .caption_linker import CaptionLinker
from .section_detector import SectionDetector
import traceback
from graph.graph_builder import GraphBuilder
from embeddings.embedder import Embedder
from retrieval.vector_search import VectorSearch
from chunking.chunker import Chunker, NormalizedChunk


class IngestionPipeline:
    """Orchestrates the complete PDF ingestion process."""
    
    def __init__(self, db: Session):
        self.db = db
        self.file_store = FileStore()
    
    def process_document(self, document_id: str) -> bool:
        """Process a single document through the complete pipeline."""
        try:
            # Get document from DB
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            # Update status
            document.status = "processing"
            self.db.commit()
            
            pdf_path = document.file_path
            
            # Step 1: Extract text blocks
            print(f"[1/10] Extracting text blocks...")
            parser = PDFParser(pdf_path)
            text_blocks = parser.extract_text_blocks()
            page_count = parser.page_count
            parser.close()
            
            # Step 2: OCR fallback for low-text pages
            print(f"[2/10] Performing OCR fallback...")
            ocr = OCRFallback(pdf_path)
            for page_num in range(page_count):
                if ocr.needs_ocr(page_num):
                    ocr_blocks = ocr.ocr_page(page_num)
                    text_blocks.extend(ocr_blocks)
            ocr.close()

            # Step 3: Detect sections early so all downstream stages can use section context
            print(f"[3/10] Detecting sections...")
            section_detector = SectionDetector()
            text_blocks = section_detector.detect_sections(text_blocks)
            
            # Step 4: Extract figures
            print(f"[4/10] Extracting figures...")
            fig_extractor = FigureExtractor(pdf_path, str(document_id))
            figures = fig_extractor.extract_figures()
            fig_extractor.close()
            
            # Step 5: Extract tables
            print(f"[5/10] Extracting tables...")
            table_extractor = TableExtractor(pdf_path)
            tables = table_extractor.extract_tables()
            table_extractor.close()
            
            # Step 6: Detect equations
            print(f"[6/10] Detecting equations...")
            eq_detector = EquationDetector()
            equations = eq_detector.detect_equations(text_blocks)
            
            # Step 7: Link captions
            print(f"[7/10] Linking captions...")
            caption_linker = CaptionLinker()
            captions = caption_linker.link_captions(text_blocks, figures, tables)
            
            # Step 8: Create chunks
            print(f"[8/10] Creating chunks...")
            chunks = self._create_chunks(
                document_id,
                text_blocks,
                figures,
                tables,
                equations,
                captions
            )
            
            # Save chunks to DB
            for chunk in chunks:
                self.db.add(chunk)
            self.db.commit()
            
            # Step 9: Build knowledge graph
            print(f"[9/10] Building knowledge graph...")
            normalized_chunks = [Chunker.from_db_chunk(chunk) for chunk in chunks]
            graph_builder = GraphBuilder(str(document_id))
            graph_builder.build_graph(normalized_chunks)
            graph_builder.save_graph()
            
            stats = graph_builder.get_graph_stats()
            print(f"  Graph: {stats['total_nodes']} nodes, {stats['total_edges']} edges")
            
            # Step 10: Create embeddings and index
            print(f"[10/10] Creating embeddings and indexing...")
            vector_search = VectorSearch()
            
            # Prepare chunks for indexing
            chunks_for_indexing = []
            for nc in normalized_chunks:
                chunks_for_indexing.append({
                    'chunk_id': str(nc.chunk_id),
                    'document_id': str(nc.document_id),
                    'chunk_type': nc.chunk_type,
                    'page_number': nc.page_number,
                    'section_title': nc.section_title,
                    'content': nc.content,
                    'caption': nc.caption,
                    'image_path': nc.image_path,
                    'chunk_index': nc.chunk_index,
                    'embedding_text': nc.to_embedding_text()
                })
            
            vector_search.index_chunks(chunks_for_indexing)
            
            # Update document status
            document.status = "ready"
            document.page_count = page_count
            self.db.commit()
            
            print(f"✓ Document {document_id} processed successfully")
            print(f"  - Text blocks: {len(text_blocks)}")
            print(f"  - Figures: {len(figures)}")
            print(f"  - Tables: {len(tables)}")
            print(f"  - Equations: {len(equations)}")
            print(f"  - Captions: {len(captions)}")
            print(f"  - Total chunks: {len(chunks)}")
            print(f"  - Graph nodes: {stats['total_nodes']}")
            print(f"  - Graph edges: {stats['total_edges']}")
            
            return True
  
        except Exception as e:
            print(f"✗ Error processing document {document_id}: {e}")
            traceback.print_exc()
            
            # Update document with error
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                document.error_message = str(e)
                self.db.commit()
            
            return False
    
    def _create_chunks(
        self,
        document_id: str,
        text_blocks: List[TextBlock],
        figures: List,
        tables: List,
        equations: List,
        captions: List
    ) -> List[Chunk]:
        """Convert extracted elements into Chunk objects."""
        chunks = []
        chunk_index = 0
        
        # Create chunks from text blocks
        for block in text_blocks:
            section_title = block.metadata.get('section_title')
            
            chunks.append(Chunk(
                document_id=document_id,
                chunk_type='text',
                content=block.text,
                page_number=block.page_number,
                section_title=section_title,
                bbox=block.bbox,
                extra_metadata={'font_size': block.font_size, 'font_name': block.font_name},
                chunk_index=chunk_index
            ))
            chunk_index += 1
        
        # Create chunks from figures
        for fig in figures:
            # Find caption for this figure
            caption_text = None
            for cap in captions:
                if cap.caption_type == 'figure' and cap.target_bbox == fig.bbox:
                    caption_text = cap.text
                    break
            
            chunks.append(Chunk(
                document_id=document_id,
                chunk_type='figure',
                content=caption_text or f"Figure on page {fig.page_number}",
                page_number=fig.page_number,
                caption=caption_text,
                image_path=fig.image_path,
                bbox=fig.bbox,
                extra_metadata={**fig.metadata, 'fig_index': fig.fig_index},
                chunk_index=chunk_index
            ))
            chunk_index += 1
        
        # Create chunks from tables
        for table in tables:
            # Find caption for this table
            caption_text = None
            for cap in captions:
                if cap.caption_type == 'table' and cap.target_bbox == table.bbox:
                    caption_text = cap.text
                    break
            
            # Convert table to text representation
            table_text = self._table_to_text(table.rows)
            
            chunks.append(Chunk(
                document_id=document_id,
                chunk_type='table',
                content=table_text,
                page_number=table.page_number,
                caption=caption_text,
                bbox=table.bbox,
                extra_metadata={**table.metadata, 'table_index': table.table_index, 'rows': table.rows},
                chunk_index=chunk_index
            ))
            chunk_index += 1
        
        # Create chunks from equations
        for eq in equations:
            chunks.append(Chunk(
                document_id=document_id,
                chunk_type='equation',
                content=eq.content,
                page_number=eq.page_number,
                bbox=eq.bbox,
                extra_metadata={**eq.metadata, 'equation_index': eq.equation_index},
                chunk_index=chunk_index
            ))
            chunk_index += 1
        
        return chunks
    
    def _table_to_text(self, rows: List[List[str]]) -> str:
        """Convert table rows to readable text."""
        if not rows:
            return ""
        
        # First row is typically header
        text_parts = []
        if len(rows) > 0:
            header = " | ".join(str(cell) for cell in rows[0] if cell)
            text_parts.append(f"Header: {header}")
        
        # Remaining rows
        for i, row in enumerate(rows[1:], 1):
            row_text = " | ".join(str(cell) for cell in row if cell)
            text_parts.append(f"Row {i}: {row_text}")
        
        return "\n".join(text_parts)