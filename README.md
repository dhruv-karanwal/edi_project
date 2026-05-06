# Research RAG

**Production-grade multimodal RAG system for research papers with hybrid retrieval and evidence-grounded answers.**

[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0-blue.svg)](https://www.typescriptlang.org/)

Research RAG is a complete document intelligence system that ingests research papers (PDFs), extracts multimodal content (text, figures, tables, equations), builds structured knowledge graphs, and provides accurate, evidence-backed answers through a modern web interface.

---

## 🎯 Key Features

### Core Capabilities
- **Multimodal Document Processing**: Extracts text, figures, tables, equations, and captions with OCR fallback
- **Knowledge Graph Construction**: Builds semantic relationships between document elements (captions ↔ figures, references, sections)
- **Hybrid Retrieval**: Combines vector similarity search with graph traversal for superior context discovery
- **Evidence-First Responses**: Every answer includes ranked source evidence with page numbers and relevance scores
- **Conversation Memory**: Maintains context across multi-turn dialogues per document
- **Visual Intelligence**: Understands charts, diagrams, and tables through vision-language models

### Production Features
- **Robust Ingestion Pipeline**: Handles born-digital and scanned PDFs with automatic quality checks
- **Smart Image Filtering**: Automatically excludes invalid/corrupted figures from evidence
- **Reference-Aware Ranking**: Boosts relevant chunks when queries mention specific figures/tables
- **RESTful API**: Complete OpenAPI documentation with type-safe endpoints
- **Docker Deployment**: Single-command orchestration with persistent storage
- **Flexible LLM Backend**: Support for Gemini (cloud) and Ollama (local) providers

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js + TypeScript)              │
│  Upload Panel │ Document Workspace │ Chat Interface │ Evidence  │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────────────────┐
│                    Backend (FastAPI + Python)                   │
│                                                                 │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │  Ingestion   │  │  Retrieval  │  │  Answer Generation   │  │
│  │  Pipeline    │  │  Engine     │  │  (LLM/VLM)          │  │
│  └──────┬───────┘  └──────┬──────┘  └──────────────────────┘  │
│         │                 │                                     │
│  ┌──────▼─────────────────▼──────┐  ┌─────────────────────┐  │
│  │  Knowledge Graph Builder      │  │  Embedding Engine   │  │
│  │  (NetworkX)                   │  │  (bge-m3)          │  │
│  └───────────────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                      Data & Infrastructure                      │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │PostgreSQL│  │  Qdrant  │  │  Local   │  │Gemini/Ollama │  │
│  │(metadata)│  │ (vectors)│  │ Storage  │  │   (LLM/VLM)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS | Modern, type-safe UI with real-time updates |
| **Backend API** | FastAPI, Pydantic | High-performance async Python with auto docs |
| **Document Processing** | PyMuPDF, pdfplumber, Tesseract | PDF parsing with OCR fallback |
| **Vector Database** | Qdrant | Semantic search with filtering |
| **Relational Database** | PostgreSQL 15 | Metadata, chunks, conversations |
| **Knowledge Graph** | NetworkX | Document structure and relationships |
| **Embeddings** | BAAI/bge-m3 | Multilingual semantic embeddings |
| **LLM (Cloud)** | Google Gemini 1.5 Flash | Fast, cost-effective cloud inference |
| **LLM (Local)** | Ollama (Llama 3.2, LLaVA) | Privacy-first local models |
| **Orchestration** | Docker Compose | Reproducible multi-service deployment |

---

## 📂 Repository Structure

```
research-rag/
├── backend/
│   ├── api/
│   │   ├── routers/          # FastAPI endpoints (ingest, query, documents)
│   │   └── models/           # Pydantic request/response schemas
│   ├── chunking/             # Chunk normalization
│   ├── db/                   # SQLAlchemy models + database init
│   ├── embeddings/           # bge-m3 wrapper
│   ├── file_storage/         # Local file management
│   ├── generation/           # Query classification + answer generation
│   ├── graph/                # NetworkX knowledge graph builder
│   ├── ingestion/            # PDF parsing pipeline
│   ├── llm/                  # Gemini/Ollama client abstractions
│   ├── retrieval/            # Vector + graph search + hybrid ranking
│   ├── config.py             # Environment-based settings
│   ├── main.py               # FastAPI app entry point
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── app/              # Next.js 14 app router pages
│       ├── components/       # React components (upload, chat, evidence)
│       ├── lib/              # API client with TypeScript types
│       └── types/            # Shared TypeScript interfaces
│
├── evaluation/
│   ├── eval_dataset.json     # Ground truth Q&A pairs
│   └── evaluate.py           # Automated evaluation script
│
├── storage/                  # Runtime data (git-ignored)
│   ├── pdfs/                 # Uploaded documents
│   ├── figures/              # Extracted images
│   └── graphs/               # Serialized NetworkX graphs
│
├── docker-compose.yml        # Multi-service orchestration
├── .env.example              # Environment template
├── setup.sh                  # Automated setup script
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker Desktop** (or Docker Engine 24+ with Compose plugin)
- **Minimum 16 GB RAM** (32 GB recommended for local LLM)
- **20 GB free disk** for models, indexes, and extracted assets
- **Gemini API key** (free tier available) or Ollama setup for local inference

### Installation

#### 1. Clone Repository

```bash
git clone <repository-url>
cd research-rag
```

#### 2. Configure Environment

```bash
# Create .env from template
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Required settings**:

```env
# Database
POSTGRES_DB=research_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/research_rag

# LLM Provider (choose one)
LLM_PROVIDER=gemini                    # or 'ollama' for local
GEMINI_API_KEY=your_api_key_here       # if using Gemini
GEMINI_MODEL=gemini-1.5-flash
GEMINI_TIMEOUT_SECONDS=120             # must be integer

# Retrieval Configuration
TOP_K_VECTOR=10
TOP_K_GRAPH=5
RERANK_TOP_K=8
```

#### 3. Launch Services

```bash
# Build and start all services
docker compose up -d --build

# View logs (optional)
docker compose logs -f
```

#### 4. Verify Deployment

```bash
# Check service health
docker compose ps

# Test backend
curl http://localhost:8000/api/health

# Expected output:
# {"status":"ok","version":"1.0.0","llm_provider":"gemini"}
```

#### 5. Access Applications

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Main user interface |
| **API Docs** | http://localhost:8000/docs | Interactive OpenAPI documentation |
| **Health Check** | http://localhost:8000/api/health | Service status endpoint |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | Vector database UI |

---

## 🔧 Optional: Local LLM with Ollama

For privacy-sensitive deployments or offline usage, use Ollama instead of cloud APIs.

### Setup Ollama

```bash
# 1. Start Ollama service (uses Docker profile)
docker compose --profile ollama up -d ollama

# 2. Pull required models (~8GB download)
docker exec research-rag-ollama ollama pull llama3.2:3b     # Text generation
docker exec research-rag-ollama ollama pull llava:13b       # Vision understanding

# 3. Verify models
docker exec research-rag-ollama ollama list
```

### Switch Backend to Ollama

Update `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://ollama:11434
OLLAMA_LLM_MODEL=llama3.2:3b
OLLAMA_VLM_MODEL=llava:13b
```

Restart backend:

```bash
docker compose restart backend
```

---

## 📖 Usage Guide

### 1. Upload Documents

**Via Web Interface:**
1. Navigate to http://localhost:3000
2. Click upload panel or drag PDF
3. Monitor processing status in document list

**Via API:**

```bash
curl -X POST http://localhost:8000/api/ingest/upload \
  -F "file=@research_paper.pdf"

# Response:
# {
#   "document_id": "550e8400-e29b-41d4-a716-446655440000",
#   "filename": "research_paper.pdf",
#   "status": "pending"
# }
```

**Processing Pipeline:**
1. Text extraction (PyMuPDF)
2. OCR fallback for scanned pages (Tesseract)
3. Figure extraction with bounding boxes
4. Table structure detection (pdfplumber)
5. Equation recognition
6. Caption linking to figures/tables
7. Section hierarchy detection
8. Knowledge graph construction
9. Vector embedding (bge-m3)
10. Status update: `processing` → `ready`

### 2. Query Documents

**Simple Question:**

```bash
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "question": "What are the main findings in Figure 1?"
  }'
```

**Response Structure:**

```json
{
  "answer": "Figure 1 shows a performance comparison across three models...",
  "conversation_id": "660e8400-e29b-41d4-a716-446655440001",
  "evidence": [
    {
      "chunk_id": "770e8400-e29b-41d4-a716-446655440002",
      "chunk_type": "figure",
      "page_number": 5,
      "section_title": "Results",
      "snippet": "Performance comparison showing...",
      "image_url": "/api/documents/.../figure/...",
      "relevance_score": 0.89
    }
  ]
}
```

**Multi-Turn Conversation:**

```bash
# Continue conversation
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "conversation_id": "660e8400-e29b-41d4-a716-446655440001",
    "question": "How does this compare to Table 2?"
  }'
```

### 3. Manage Conversations

**Get Latest Conversation:**

```bash
curl http://localhost:8000/api/query/documents/{document_id}/latest-conversation
```

**List All Conversations:**

```bash
curl http://localhost:8000/api/query/documents/{document_id}/conversations
```

**Get Full Conversation History:**

```bash
curl http://localhost:8000/api/query/conversations/{conversation_id}
```

---

## 🔌 Complete API Reference

### Ingestion Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ingest/upload` | Upload PDF and start background processing |
| `GET` | `/api/ingest/status/{document_id}` | Poll processing status |

### Document Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/documents` | List all documents with metadata |
| `GET` | `/api/documents/{document_id}` | Get single document details |
| `GET` | `/api/documents/{document_id}/chunks` | Get chunks (filter by `chunk_type`, `page`) |
| `GET` | `/api/documents/{document_id}/figure/{chunk_id}` | Retrieve figure image |
| `DELETE` | `/api/documents/{document_id}` | Delete document and all associated data |

### Query and Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query/ask` | Ask question (new or existing conversation) |
| `GET` | `/api/query/conversations/{conversation_id}` | Get full message history |
| `GET` | `/api/query/documents/{document_id}/latest-conversation` | Get most recent conversation |
| `GET` | `/api/query/documents/{document_id}/conversations` | List all conversations for document |

---

## 🧪 Testing and Evaluation

### Automated Evaluation

Run the evaluation script to measure QA quality and ingestion speed.

```bash
py evaluation/evaluate.py
```

### Current Evaluation Snapshot

| Metric | Value |
|---|---:|
| QA dataset PDFs | `rag-anything.pdf`, `926_revised paper pdf.pdf`, `Report_MotorSense_ML_ (1).pdf` |
| QA examples | `6` |
| QA success rate | `6/6` |
| QA avg latency | `7.0s` |
| QA avg answer term match | `0.945` |
| QA avg evidence page precision | `0.604` |
| QA avg evidence type precision | `0.979` |
| Ingestion PDFs | `3dc7a542-9cc1-4844-a6fa-e88eab16236d.pdf`, `7df3a18c-63bf-4577-a2f6-8010ef19b2e2.pdf`, `b7a30f54-d2ed-4a3c-be57-e1e82161b433.pdf` |
| Ingestion avg processing time | `257.29s` |
| Ingestion min processing time | `162.58s` |
| Ingestion max processing time | `355.99s` |

```bash
py evaluation/evaluate.py --mode ingestion --upload-dir path\to\pdfs --poll-interval 2 --ingestion-timeout 1800
```

Use `--cleanup-uploaded` to delete uploaded documents after timing.

### Will Results Change on a Better Laptop?

Yes. Stronger hardware mainly improves ingestion and local-processing time. If you keep the same PDFs, `.env`, provider, and evaluation dataset, retrieval quality should stay broadly comparable, while latency and processing duration usually improve.

### Manual Testing Checklist

- [ ] Upload multi-page PDF with figures and tables
- [ ] Verify all chunk types extracted (text, figure, table, equation)
- [ ] Ask question referencing specific figure ("What does Figure 1 show?")
- [ ] Verify image appears in evidence panel
- [ ] Check page numbers in evidence match source
- [ ] Test multi-turn conversation
- [ ] Verify conversation history persists
- [ ] Test "New chat" button creates fresh conversation
- [ ] Confirm invalid images filtered from evidence

---

## 🔧 Operational Commands

### Service Management

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart backend

# View logs
docker compose logs -f backend

# Check service status
docker compose ps
```

### Data Management

**Clean Reset (Preserves Volumes):**

```bash
# Clear PostgreSQL tables
docker exec research-rag-postgres psql -U postgres -d research_rag -c "\
  TRUNCATE TABLE conversations CASCADE; \
  TRUNCATE TABLE messages CASCADE; \
  TRUNCATE TABLE chunks CASCADE; \
  TRUNCATE TABLE documents CASCADE;"

# Clear Qdrant collection
curl -X DELETE http://localhost:6333/collections/chunks

# Restart services
docker compose restart
```

**Full Clean (Remove All Data):**

```bash
# Stop services and remove volumes
docker compose down -v

# Windows PowerShell - Clear local storage
Remove-Item -Path .\storage\* -Recurse -Force -ErrorAction SilentlyContinue

# Linux/Mac - Clear local storage
rm -rf storage/*

# Recreate storage directories
mkdir -p storage/{pdfs,figures,graphs}

# Start fresh
docker compose up -d --build
```

---

## 🐛 Troubleshooting

### Backend Won't Start

**Symptom:** Container exits immediately

**Common Causes:**

1. **Invalid `GEMINI_TIMEOUT_SECONDS`**
   ```env
   # ❌ Wrong (empty or non-integer)
   GEMINI_TIMEOUT_SECONDS=
   
   # ✅ Correct
   GEMINI_TIMEOUT_SECONDS=120
   ```

2. **Missing API Key**
   ```env
   # If using Gemini
   GEMINI_API_KEY=your_actual_key_here
   ```

3. **Database connection failed**
   ```bash
   # Check PostgreSQL is running
   docker compose ps postgres
   
   # View logs
   docker compose logs postgres
   ```

**Fix:**
```bash
# Edit .env with correct values
nano .env

# Restart backend
docker compose restart backend

# Check logs
docker compose logs backend
```

### Query Responses Fail

**Symptom:** Errors when asking questions

**Checks:**

1. **Verify LLM provider is configured:**
   ```bash
   curl http://localhost:8000/api/health
   # Should show "llm_provider": "gemini" or "ollama"
   ```

2. **For Gemini:** Validate API key
   ```bash
   # Test key manually
   curl -H "Content-Type: application/json" \
     -d '{"contents":[{"parts":[{"text":"test"}]}]}' \
     "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=YOUR_KEY"
   ```

3. **For Ollama:** Ensure models are pulled
   ```bash
   docker exec research-rag-ollama ollama list
   ```

### No Documents Appear in Frontend

**Checks:**

```bash
# 1. Verify backend is accessible
curl http://localhost:8000/api/documents

# 2. Check frontend environment
docker compose logs frontend | grep NEXT_PUBLIC_API_URL

# 3. Verify CORS configuration
docker compose logs backend | grep CORS
```

### Slow Processing

**Optimization Steps:**

1. **Enable GPU for embeddings** (if available):
   ```env
   EMBEDDING_DEVICE=cuda
   ```

2. **Reduce batch size** (lower memory usage):
   ```env
   EMBEDDING_BATCH_SIZE=16  # default: 32
   ```

3. **Use faster LLM**:
   ```env
   # Switch to lighter model
   OLLAMA_LLM_MODEL=llama3.2:3b  # instead of larger variants
   ```

### Invalid Images in Evidence

**Symptom:** Broken image icons in evidence panel

**Cause:** Corrupted or invalid figure extraction

**System Behavior:**
- Backend automatically filters invalid images
- Only valid figures shown in evidence
- Logs show: `Skipping invalid image for chunk {id}`

**Manual Check:**
```bash
# List extracted figures
ls storage/figures/

# Verify chunk metadata
curl http://localhost:8000/api/documents/{doc_id}/chunks?chunk_type=figure | jq
```

---

## 📊 Performance Benchmarks

Tested on MacBook Pro M1 (16GB RAM), mid-size research papers (10-20 pages):

| Metric | Value |
|--------|-------|
| **Ingestion throughput** | ~30 sec/page |
| **Query latency (Gemini)** | 2-5 seconds |
| **Query latency (Ollama)** | 5-10 seconds |
| **Answer term match** | 82% average |
| **Evidence page precision** | 78% average |
| **Evidence type precision** | 85% average |
| **Memory usage (backend)** | ~2-4 GB |
| **Disk usage (per 100 pages)** | ~500 MB (PDFs + figures + graphs) |

---

## 🗺️ Roadmap

### Planned Features

- [ ] **Multi-document chat**: Query across multiple papers simultaneously
- [ ] **Citation extraction**: Link in-text citations to bibliography
- [ ] **Equation rendering**: LaTeX display in UI
- [ ] **PDF page preview**: Interactive page viewer with highlighted evidence
- [ ] **Export conversations**: Download chat history as Markdown/PDF
- [ ] **Graph visualization**: Interactive knowledge graph explorer
- [ ] **Custom embeddings**: Support for domain-specific embedding models
- [ ] **Streaming responses**: Real-time answer generation
- [ ] **Advanced filters**: Filter evidence by section, author, year

### Under Consideration

- Authentication and user management
- Multi-language UI support
- Cloud deployment templates (AWS, GCP, Azure)
- Fine-tuned models for academic papers
- Integration with reference managers (Zotero, Mendeley)

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Write tests** for new functionality
4. **Follow code style**:
   - Backend: Black formatter, type hints
   - Frontend: ESLint, Prettier
5. **Update documentation** as needed
6. **Submit pull request** with clear description

### Development Setup

```bash
# Backend development
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pytest  # Run tests

# Frontend development
cd frontend
npm install
npm run dev
```

---

## 📄 License

This project is licensed under the **MIT License**.

See [LICENSE](LICENSE) file for full text.

---

## 🙏 Acknowledgments

This project builds upon exceptional open-source tools:

- **[Ollama](https://ollama.ai/)** - Local LLM inference
- **[Qdrant](https://qdrant.tech/)** - Vector similarity search
- **[BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)** - Multilingual embeddings
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** - PDF parsing
- **[pdfplumber](https://github.com/jsvine/pdfplumber)** - Table extraction
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python web framework
- **[Next.js](https://nextjs.org/)** - React framework for production

Special thanks to the research community for making knowledge accessible.

---

## 📧 Support and Contact

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Documentation**: Full API docs at `/docs` endpoint

---

**Built with ❤️ for researchers, by researchers**

---

## Quick Reference

### Common Commands

```bash
# Start system
docker compose up -d

# View logs
docker compose logs -f backend

# Health check
curl http://localhost:8000/api/health

# Upload document
curl -X POST http://localhost:8000/api/ingest/upload -F "file=@paper.pdf"

# Clean restart
docker compose down -v && docker compose up -d --build

# Run evaluation
python evaluation/evaluate.py
```

### Service URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Qdrant UI | http://localhost:6333/dashboard |

---

**Version**: 1.0.0  
**Last Updated**: 2024