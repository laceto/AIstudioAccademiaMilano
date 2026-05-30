FROM python:3.11-slim

WORKDIR /app

# git needed to install kitai from GitHub
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements-rag.txt .
RUN pip install --no-cache-dir -r requirements-rag.txt

COPY scripts/ ./scripts/
COPY config/ ./config/
COPY data/vectorstore/ ./data/vectorstore/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn scripts.rag.api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
