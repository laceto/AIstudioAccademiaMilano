FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt ./gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt

COPY gateway/ ./gateway/

# Cloud Run filesystem is read-only except /tmp — use /tmp/queue for job files
ENV GATEWAY_QUEUE_DIR=/tmp/queue
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "gateway.api:app", "--host", "0.0.0.0", "--port", "8080"]
