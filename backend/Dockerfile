FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN PIP_REQUIRE_HASHES=0 pip install --upgrade pip setuptools wheel

RUN PIP_REQUIRE_HASHES=0 pip install \
    --no-cache-dir \
    --default-timeout=1000 \
    --retries 10 \
    -r requirements.txt 

ENV PIP_NO_CACHE_DIR=1

# Download embedding model at build time
# RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

COPY . .

# Create storage directories
RUN mkdir -p /app/storage/pdfs /app/storage/figures /app/storage/graphs

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]