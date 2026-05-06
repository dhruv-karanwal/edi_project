import os
import shutil
from pathlib import Path
from typing import BinaryIO
from config import get_settings

settings = get_settings()

class FileStore:
    """Handles local file storage for PDFs, figures, and graphs."""
    
    def __init__(self):
        self.base_path = Path(settings.storage_path)
        self.pdf_path = self.base_path / "pdfs"
        self.figures_path = self.base_path / "figures"
        self.graphs_path = self.base_path / "graphs"
        
        # Ensure directories exist
        self.pdf_path.mkdir(parents=True, exist_ok=True)
        self.figures_path.mkdir(parents=True, exist_ok=True)
        self.graphs_path.mkdir(parents=True, exist_ok=True)
    
    def save_pdf(self, document_id: str, file: BinaryIO, filename: str) -> str:
        """Save uploaded PDF and return file path."""
        file_path = self.pdf_path / f"{document_id}.pdf"
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file, f)
        return str(file_path)
    
    def save_figure(self, document_id: str, page_num: int, fig_index: int, image_bytes: bytes) -> str:
        """Save extracted figure image and return file path."""
        filename = f"{document_id}_p{page_num}_fig{fig_index}.png"
        file_path = self.figures_path / filename
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        return str(file_path)
    
    def save_graph(self, document_id: str, graph_data: bytes) -> str:
        """Save serialized NetworkX graph and return file path."""
        file_path = self.graphs_path / f"{document_id}.pkl"
        with open(file_path, "wb") as f:
            f.write(graph_data)
        return str(file_path)
    
    def load_graph(self, document_id: str) -> bytes:
        """Load serialized graph."""
        file_path = self.graphs_path / f"{document_id}.pkl"
        with open(file_path, "rb") as f:
            return f.read()
    
    def get_pdf_path(self, document_id: str) -> str:
        """Get path to PDF file."""
        return str(self.pdf_path / f"{document_id}.pdf")
    
    def get_figure_path(self, image_path: str) -> str:
        """Get absolute path to figure."""
        return image_path
    
    def delete_document_files(self, document_id: str):
        """Delete all files for a document."""
        # Delete PDF
        pdf_file = self.pdf_path / f"{document_id}.pdf"
        if pdf_file.exists():
            pdf_file.unlink()
        
        # Delete figures
        for fig_file in self.figures_path.glob(f"{document_id}_*"):
            fig_file.unlink()
        
        # Delete graph
        graph_file = self.graphs_path / f"{document_id}.pkl"
        if graph_file.exists():
            graph_file.unlink()