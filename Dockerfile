FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data/ccc/ccc_seed.json ./data/ccc/ccc_seed.json
COPY scripts ./scripts
COPY pyproject.toml README.md .env.example ./

# Pre-build the starter CCC FAISS index so the container starts immediately
RUN python scripts/ingest_ccc.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
