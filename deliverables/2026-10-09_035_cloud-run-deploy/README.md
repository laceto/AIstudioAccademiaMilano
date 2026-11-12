# 035 — Cloud Run deploy (gateway + rag-api)

Deploy dei canali Telegram su Google Cloud Run, progetto `aistudio-milano`, regione `europe-west8`.

| Servizio | URL | Origine |
|----------|-----|---------|
| `gateway` | https://gateway-947977086404.europe-west8.run.app | `gateway/Dockerfile` |
| `rag-api` | https://rag-api-947977086404.europe-west8.run.app | `scripts/rag/Dockerfile` |

Eseguito con `scripts/deploy_cloudrun.sh` (idempotente; `--dry-run` per l'anteprima).
Verifica: `/docs` risponde 200 su entrambi, `scripts/check_telegram.py --expect-webhook pipeline`
riporta "All Telegram channels healthy" (webhook registrati, 0 update in coda).

Documentazione: `docs/cloud-run-setup.md`, `process/runbook_cloudrun.md`.

Fuori ambito: Streamlit, WhatsApp, storage persistente della coda (vedi limiti nel runbook).
