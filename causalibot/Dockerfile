# causali-bot for Cloud Run. Build from the repo root:
#   gcloud builds submit --config deploy/cloudbuild.causali.yaml --substitutions _IMAGE=...
FROM python:3.12-slim

WORKDIR /app

COPY causalibot/requirements.txt ./causalibot/requirements.txt
RUN pip install --no-cache-dir -r causalibot/requirements.txt

# Code and bankanalyst's base rules (rules.yaml guesses the category). No token and no personal rules in the
# image: Cloud Run injects the token and the webhook secret from Secret Manager.
COPY causalibot/ ./causalibot/
COPY bankanalyst/ ./bankanalyst/

ENV PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8080

# Public only because Telegram must reach it: every update needs the secret_token header, only Luigi's id is answered.
CMD ["sh", "-c", "uvicorn causalibot.app:app --host 0.0.0.0 --port ${PORT:-8080} --log-level warning"]
