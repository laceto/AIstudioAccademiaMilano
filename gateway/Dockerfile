FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt ./gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt

COPY gateway/ ./gateway/
COPY config/ ./config/
COPY process/audit/ ./process/audit/

# Cloud Run / Railway filesystems are read-only except /tmp — use /tmp/queue for job files
ENV GATEWAY_QUEUE_DIR=/tmp/queue
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["sh", "-c", "uvicorn gateway.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
