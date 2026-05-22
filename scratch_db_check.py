import sqlite3

def check_db():
    conn = sqlite3.connect('backend/research_rag.db')
    cursor = conn.cursor()
    
    print("--- DOCUMENTS ---")
    cursor.execute("SELECT id, filename, status, error_message, page_count FROM documents")
    for row in cursor.fetchall():
        print(f"ID: {row[0]}")
        print(f"Filename: {row[1]}")
        print(f"Status: {row[2]}")
        print(f"Error: {row[3]}")
        print(f"Pages: {row[4]}")
        print("-" * 40)
        
    print("\n--- CHUNKS COUNT PER DOCUMENT ---")
    cursor.execute("SELECT document_id, COUNT(*) FROM chunks GROUP BY document_id")
    for row in cursor.fetchall():
        print(f"Doc ID: {row[0]}, Chunks: {row[1]}")
    conn.close()

if __name__ == '__main__':
    check_db()
