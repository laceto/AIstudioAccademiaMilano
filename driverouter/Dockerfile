# Drive semantic router (delivery 043)
# Build from the repo root:  docker build -f driverouter/Dockerfile -t drive-router .
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY driverouter/requirements.txt .
# CPU-only torch first (explicit index), then the rest; torch is already satisfied for the second step.
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu \
 && /opt/venv/bin/pip install -r requirements.txt

# Bake the model into the image: no download on cold start, no Hugging Face call at runtime.
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV HF_HOME=/opt/models
RUN /opt/venv/bin/python -c "from sentence_transformers import SentenceTransformer as S; S('${EMBEDDING_MODEL}', device='cpu')"


FROM python:3.11-slim

ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/models \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False \
    EMBEDDING_MODEL=${EMBEDDING_MODEL} \
    CHROMA_DIR=/tmp/chroma \
    OMP_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    PORT=8000

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/models /opt/models
WORKDIR /app
COPY driverouter/__init__.py driverouter/classifier.py driverouter/main.py driverouter/

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=120s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"
# One worker: one model in memory (F1 has 1 GB RAM) and one scheduler.
CMD ["sh", "-c", "uvicorn driverouter.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
