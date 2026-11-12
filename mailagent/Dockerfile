# mailagent tidy service for Cloud Run. Build from the repo root:
#   gcloud builds submit --config deploy/cloudbuild.mailagent.yaml --substitutions _IMAGE=...
FROM python:3.12-slim

WORKDIR /app

COPY mailagent/requirements.txt ./mailagent/requirements.txt
RUN pip install --no-cache-dir -r mailagent/requirements.txt

# Code and the account list only. No token in the image: Cloud Run injects it from Secret Manager
# as the env var named by the account's options.token_env.
COPY mailagent/ ./mailagent/
COPY config/mailagent_accounts.yaml ./config/mailagent_accounts.yaml

ENV PYTHONUNBUFFERED=1 MAILAGENT_DRY_RUN=1
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8080

# Private service: only the mailagent-invoker service account (Cloud Scheduler, OIDC) may call it.
CMD ["sh", "-c", "uvicorn mailagent.server:app --host 0.0.0.0 --port ${PORT:-8080} --log-level warning"]
