FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

RUN useradd -m -u 1000 user

USER user
WORKDIR $HOME/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

EXPOSE 7860

CMD streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=7860 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
