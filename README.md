# 🧠 Neural Machine Reading with Visual Grounding for Document Understanding

A state-of-the-art **Multimodal Document Intelligence** and **Hybrid RAG** system designed for native and scanned PDF understanding. This application combines deep document layout analysis, visual grounding, multi-stage hybrid retrieval (vector semantic, lexical keyword, and visual semantic), and the reasoning power of the **Google Gemini API** to answer complex queries with high-precision visual citations.

---

## 🏗️ System Architecture

The project is built on a decoupled **FastAPI** backend and a **Next.js** (React/TypeScript) frontend. Here is a high-level representation of how ingestion, indexing, retrieval, and generation flow through the pipeline:

```
                            ┌───────────────────────────┐
                            │    Next.js UI (React)     │
                            │   Port 3000 | Tailwind    │
                            └─────────────┬─────────────┘
                                          │ (Axios REST Calls)
                                          ▼
                            ┌───────────────────────────┐
                            │   FastAPI Backend Engine  │
                            │        Port 8000          │
                            └───────┬───────────┬───────┘
                                    │           │
         ┌──────────────────────────▼┐         ┌▼──────────────────────────┐
         │   Ingestion & Parsing     │         │   Multi-Stage Retrieval   │
         │ • PyMuPDF Rasterizer      │         │ • BM25 Keyword Search     │
         │ • surya AI Layout Engine  │         │ • FAISS Dense Vector      │
         │ • OpenCV & OCR Engine     │         │ • CLIP Visual Search      │
         │ • On-Demand Figure Crops  │         │ • LayoutLMv3 Multimodal   │
         └───────────────────────────┘         └───────────────────────────┘
                                    │           │
                                    └─────┬─────┘
                                          │ (Multimodal Prompts & Visual Crops)
                                          ▼
                            ┌───────────────────────────┐
                            │      Google Gemini        │
                            │   (gemini-2.5-flash)      │
                            └───────────────────────────┘
```

---

## 🌟 Key Technical Features

### 1. 📂 Zero System-Level Dependencies (PyMuPDF Rasterizer)
Traditionally, PDF-to-image rasterization relies on system-level binaries like **Poppler** (`pdftoppm`), which complicates installation across different operating systems. This codebase uses a high-performance, C-based rasterization engine built directly into **PyMuPDF** (`fitz`), enabling pure Python installation on Windows, Linux, and MacOS without any external binaries.

### 2. 🔲 Unified Relative Coordinate Canvas (0–1000 Grid)
Every extracted bounding box coordinate (for text zones, figures, tables, and equations) is scaled onto a relative `0–1000` grid normalized against each page's specific height and width. This standardizes coordinate data across varying page sizes, allowing the Next.js frontend to overlay pixel-perfect highlight boxes responsively at any view scale without complex math.

### 3. 🖼️ On-Demand (Lazy) Figure & Table Cropping
To save CPU cycles, memory, and disk space during ingestion, the backend does not pre-crop figures or tables. Instead, it stores their relative coordinates and parent page paths. When the user reviews a chunk or triggers a query, the `/figure/{chunk_id}` endpoint crops the image region on-the-fly, adding a subtle `10px` padding for visual aesthetics.

### 4. 🧠 Advanced AI Layout Detection (surya-ocr)
Powered by the state-of-the-art **surya** layout models, the ingestion pipeline automatically partitions pages into semantic blocks, including:
* **Headers, Section Titles, and Title blocks** (used to automatically inherit hierarchy context)
* **Standard Paragraph Text & Lists**
* **Visual Figures & Graphics**
* **Tables & Tabular Regions**
* **Captions and Footnotes**
* **Mathematical Formulas & Equations**

*Fallback*: If the `surya` layout package is not installed or disabled, the backend gracefully falls back to high-fidelity **PyMuPDF structural heuristics**.

### 5. 🔍 Multi-Stage Hybrid Retrieval Engine
The legacy semantic vector search is upgraded to a multi-stage hybrid engine combining three complementary retrieval methods:
* **Dense Vector Semantic Search (FAISS)**: Uses SentenceTransformers (`all-MiniLM-L6-v2`) to perform high-speed concept-level matching (best for paraphrased queries).
* **Lexical Keyword Search (BM25)**: Uses the `rank-bm25` algorithm to perform exact term matching (best for technical numbers, abbreviations, acronyms, and proper nouns).
* **Cross-Modal Visual Search (OpenAI CLIP)**: Uses `CLIP-ViT-B-32` to create multi-modal representations of image regions (figures/tables). This allows text-to-image queries, matching natural language directly against visual content even if surrounding text is sparse or absent.
* **LayoutLMv3 (Optional Multimodal)**: Embeds document text, 2D layout boxes, and visual patches jointly into a unified 768-dimensional representation.

Scores from all active search methods are min-max normalized and fused using a customizable weighted linear combination:
$$\text{Score} = w_{\text{bm25}} \cdot S_{\text{bm25}} + w_{\text{faiss}} \cdot S_{\text{faiss}} + w_{\text{clip}} \cdot S_{\text{clip}}$$

### 6. 🚀 OpenCV-Enhanced OCR Pipeline
Scanned or low-text pages are automatically passed through an advanced **OpenCV image preprocessing pipeline** (grayscale conversion, adaptive Gaussian thresholding, deskewing, and noise removal) before undergoing OCR. The backend dynamically uses **Tesseract OCR** with a lazy-loaded **EasyOCR** fallback, making it resilient across edge cases and cloud environments.

---

## 🛠️ Prerequisites

To run this system locally on **Windows**, ensure you have:
1. **Python 3.10+** (Ensure Python is added to your Windows PATH environment variable).
2. **Node.js 18+** & `npm` (for running the React frontend).
3. **Tesseract OCR** (Optional, recommended for OCR fallback on scanned documents):
   * Download the Windows installer from [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
   * Install it (default installation path is usually `C:\Program Files\Tesseract-OCR\tesseract.exe`).
   * Add `C:\Program Files\Tesseract-OCR` to your User/System **PATH** environment variables.
   * *Note*: If Tesseract is not found, the backend will lazily use EasyOCR automatically!

---

## 🚀 Setup & Launch Instructions

### Step 1: Clone and Environment Setup
Clone this repository to your local machine and set up environment variables:

1. Create a `.env` file inside the `backend/` directory by copying the example:
   ```powershell
   # Run from the root directory
   Copy-Item .env.example backend/.env
   ```
2. Open `backend/.env` in your editor and paste your **Google Gemini API Key**:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key
   ```

---

### Step 2: Running the Python FastAPI Backend

1. Navigate to the `backend/` directory:
   ```powershell
   cd backend
   ```
2. Create a virtual environment:
   ```powershell
   python -m venv .venv
   ```
3. Activate the virtual environment:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
4. Install the required backend dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
5. Start the FastAPI development server:
   ```powershell
   python main.py
   ```
   * The backend will automatically run on **`http://localhost:8000`**.
   * Interactive API Swagger documentation is available at **`http://localhost:8000/docs`**.
   * Run-time diagnostics and features can be verified at **`http://localhost:8000/health`**.

---

### Step 3: Running the Next.js Frontend

1. Open a new terminal window and navigate to the `frontend/` directory:
   ```powershell
   cd frontend
   ```
2. Create the `.env` configuration file:
   ```powershell
   Copy-Item .env.example .env
   ```
   *(Ensure the file contains `NEXT_PUBLIC_API_URL=http://localhost:8000/api`)*
3. Install standard Node dependencies:
   ```powershell
   npm install
   ```
4. Run the frontend development server:
   ```powershell
   npm run dev
   ```
   * The web application will launch on **`http://localhost:3000`**.
   * Open your browser and navigate to **`http://localhost:3000`** to begin exploring documents.

---

## ⚙️ Advanced Configuration (backend/.env)

You can customize the pipeline models, weights, and active pipelines directly within `backend/.env`:

| Key | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./research_rag.db` | Local SQLite relational database URL. |
| `ENABLE_OCR_PREPROCESSING` | `true` | Enable OpenCV contrast/skew enhancement. |
| `PREFER_EASYOCR` | `true` | Prefer EasyOCR over Tesseract if both exist. |
| `ENABLE_LAYOUT_DETECTION` | `true` | Toggle surya AI-powered layout partitioner. |
| `ENABLE_CLIP` | `true` | Enable OpenAI CLIP multi-modal visual embeddings. |
| `ENABLE_HYBRID_RETRIEVAL` | `true` | Toggle Multi-stage Retrieval (BM25 + Vector + CLIP). |
| `BM25_WEIGHT` | `0.30` | Keyword matching contribution score weight. |
| `FAISS_WEIGHT` | `0.50` | Text semantic vector contribution score weight. |
| `CLIP_WEIGHT` | `0.20` | Visual semantic contribution score weight. |
| `ENABLE_LAYOUTLM` | `false` | Enable LayoutLMv3 (Set `true` if GPU is available). |

---

## 📄 License & Credits
Developed as an advanced **Neural Machine Reading** system for document understanding. Leveraging Google's **Gemini models** for generation, and state-of-the-art vision models for layout/text representation. Built with premium design, fast response pipelines, and clean modular architecture.
