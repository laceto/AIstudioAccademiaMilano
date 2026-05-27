FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TA_LIB_VERSION=0.4.0 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# TA-Lib C library (required by techa deep-analysis; harmless if techa not used)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential wget ca-certificates curl \
    && wget -qO- "https://prdownloads.sourceforge.net/ta-lib/ta-lib-${TA_LIB_VERSION}-src.tar.gz" \
       | tar -xz -C /tmp \
    && cd /tmp/ta-lib && ./configure --prefix=/usr && make && make install \
    && rm -rf /tmp/ta-lib /var/lib/apt/lists/* \
    && useradd -m -u 1000 user

USER user
WORKDIR $HOME/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Optional: uncomment to enable /api/analysis and the techa deep-analysis panel
# RUN pip install --no-cache-dir --user \
#     'techa @ git+https://github.com/laceto/techa.git@main' \
#     openai>=1.40 langchain-openai>=0.2 langgraph>=0.2

COPY --chown=user . .

ENV PORT=8501
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:${PORT}/_stcore/health || exit 1

# Honour $PORT so the same image works on HF Spaces (8501) and Cloud Run ($PORT, typically 8080).
CMD streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=${PORT} \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
