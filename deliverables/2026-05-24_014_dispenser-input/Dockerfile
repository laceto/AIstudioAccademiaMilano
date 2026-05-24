FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user

USER user
WORKDIR $HOME/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . ./

ENV PORT=8501
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:${PORT}/_stcore/health || exit 1

# Honours $PORT so the same image runs on HF Spaces (8501) and Cloud Run ($PORT).
# XSRF protection stays ON (Streamlit default) — this app handles payments + PII.
CMD streamlit run main.py \
    --server.address=0.0.0.0 \
    --server.port=${PORT} \
    --server.enableCORS=false
