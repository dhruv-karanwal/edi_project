# Neural Machine Reading with Visual Grounding for Document Understanding

A state-of-the-art Multimodal Document Intelligence system. This application accepts native and scanned PDFs, rasterizes pages, performs layout-aware OCR (Tesseract with an EasyOCR fallback), indexes semantic blocks in a high-speed local vector database (FAISS), crops visual figure/table regions on-the-fly, and leverages the Google Gemini Vision API to answer user queries with precise visual grounding citations.

---

## 🏗️ Project Architecture

```
                          ┌───────────────────────────┐
                          │    Next.js UI (React)     │
                          │   Port 3000 / Tailwinds   │
                          └─────────────┬─────────────┘
                                        │ (Axios REST Calls)
                                        ▼
                          ┌───────────────────────────┐
                          │   FastAPI Backend Engine  │
                          │        Port 8000          │
                          └───────┬───────────┬───────┘
                                  │           │
       ┌──────────────────────────▼┐         ┌▼──────────────────────────┐
       │   Ingestion & parsing     │         │   Semantic Search & RAG   │
       │ • PyMuPDF Rasterizer      │         │ • SentenceTransformers    │
       │ • Layout OCR (Tesseract)  │         │ • FAISS Local Indexing    │
       │ • On-Demand Figure Crops  │         │ • SQLite Relational DB    │
       └───────────────────────────┘         └───────────────────────────┘
                                  │           │
                                  └─────┬─────┘
                                        │ (Multimodal Prompts & Crops)
                                        ▼
                          ┌───────────────────────────┐
                          │   Google Gemini API       │
                          │    (gemini-1.5-flash)     │
                          └───────────────────────────┘
```

---

## 🛠️ Prerequisites

To run this system locally on **Windows**, ensure you have:
1. **Python 3.10+** (Ensure Python is added to your Windows PATH).
2. **Node.js 18+** & npm.
3. **Tesseract OCR** (Recommended for image/scanned PDF processing):
   * Download the Windows installer from [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
   * Install it (default path is usually `C:\Program Files\Tesseract-OCR\tesseract.exe`).
   * Add `C:\Program Files\Tesseract-OCR` to your User/System **PATH** environment variables.
   * *Fallback*: If Tesseract is not installed or configured, the backend will automatically lazy-load **EasyOCR** to parse layouts!

---

## 🚀 Setup & Launch Instructions

### Step 1: Clone and Environment Setup
Create the `.env` file in the `backend/` directory by copying the template:
```powershell
# Copy the env template (run from root directory)
Copy-Item .env.example backend/.env
```
Open `backend/.env` and paste your **Google Gemini API Key**:
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

4. Install the backend dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

5. Start the FastAPI development server:
   ```powershell
   python main.py
   ```
   * The backend will run on **`http://localhost:8000`**.
   * You can access the interactive API docs at **`http://localhost:8000/docs`**.

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
   *(Ensure it contains `NEXT_PUBLIC_API_URL=http://localhost:8000/api`)*

3. Install node dependencies:
   ```powershell
   npm install
   ```

4. Run the frontend development server:
   ```powershell
   npm run dev
   ```
   * The web application will launch on **`http://localhost:3000`**.

---

## 🌟 Key Technical Features

* **Zero external Poppler dependency**: Traditionally, converting PDF pages to images requires installing system-level Poppler binaries. This project uses `PyMuPDF` (fitz)'s high-speed C-based rasterization directly inside Python, ensuring a seamless, pure-pip installation on Windows.
* **Unified Bounding Box Grid (0-1000)**: Coordinates extracted from PDFs or OCR systems are scaled onto a relative `0-1000` canvas. This allows the Next.js frontend to overlay highlights accurately on any view size without complex recalculations.
* **On-Demand (Lazy) Figure Cropping**: The system processes documents quickly by extracting coordinates during ingestion and only cropping specific images when requested by the frontend `/figure` API endpoint, conserving CPU cycles.
* **Resilient Multimodal Prompts**: Grounding evidence is parsed as a hybrid multimodal package. When a user asks about a figure, the actual cropped visual image is loaded as a binary token array, combined with conversational history, and reasoned by Gemini Vision.
