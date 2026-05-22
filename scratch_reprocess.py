import sys
import os
import traceback

# Add backend to path
sys.path.append('backend')
os.environ["DATABASE_URL"] = "sqlite:///c:/Users/HP/Desktop/Projects/edi_project/backend/research_rag.db"
os.environ["STORAGE_PATH"] = "c:/Users/HP/Desktop/Projects/edi_project/backend/storage"
os.environ["UPLOADS_DIR"] = "c:/Users/HP/Desktop/Projects/edi_project/backend/storage/uploads"
os.environ["PAGES_DIR"] = "c:/Users/HP/Desktop/Projects/edi_project/backend/storage/pages"
os.environ["FIGURES_DIR"] = "c:/Users/HP/Desktop/Projects/edi_project/backend/storage/figures"
os.environ["VECTOR_DIR"] = "c:/Users/HP/Desktop/Projects/edi_project/backend/storage/vector_indices"


from backend.models.db_models import SessionLocal, Document
from backend.services.pdf_service import PDFService
from backend.rag.retriever import Retriever

def test_pipeline():
    db = SessionLocal()
    doc_id = 'a6adca86-281f-4703-9ba1-5f2f0dae8151'
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        print("Document not found!")
        return
        
    print(f"Testing pipeline for: {doc.filename}")
    pdf_path = os.path.join('backend', 'storage', 'uploads', f"{doc_id}.pdf")
    print(f"PDF Path: {pdf_path}")
    print(f"File exists: {os.path.exists(pdf_path)}")
    
    pdf_service = PDFService()
    retriever = Retriever()
    
    try:
        print("\n--- 1. Rendering Pages ---")
        page_images = pdf_service.render_pages(pdf_path)
        print(f"Rendered {len(page_images)} pages: {page_images[:2]}...")
        
        print("\n--- 2. Extracting Layout ---")
        chunks = pdf_service.extract_layout(pdf_path, page_images)
        print(f"Extracted {len(chunks)} chunks.")
        
        print("\n--- 3. Indexing Chunks ---")
        retriever.index_document_chunks(db, doc_id, chunks)
        print("Indexing completed successfully!")
        
    except Exception as e:
        print("\n!!! ERROR IN PIPELINE !!!")
        print(f"Exception type: {type(e)}")
        print(f"Exception message: {e}")
        print("\nTraceback:")
        traceback.print_exc()
        
    finally:
        db.close()

if __name__ == '__main__':
    test_pipeline()
