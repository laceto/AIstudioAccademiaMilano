FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TA_LIB_VERSION=0.4.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential wget ca-certificates \
    && wget -qO- "https://prdownloads.sourceforge.net/ta-lib/ta-lib-${TA_LIB_VERSION}-src.tar.gz" \
       | tar -xz -C /tmp \
    && cd /tmp/ta-lib && ./configure --prefix=/usr && make && make install \
    && rm -rf /tmp/ta-lib /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./

EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]
