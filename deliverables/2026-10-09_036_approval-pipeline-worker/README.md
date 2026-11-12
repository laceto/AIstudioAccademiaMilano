# 036 — Approvazione da Telegram e worker asincrono della pipeline

Il codice sta in `gateway/`; questa cartella è il punto d'ingresso per capire come funziona e come si gestisce.
Audit: `process/audit/2026-10-09_036_approval-pipeline-worker.md`. Piano e stato: `docs/plans/luigi-approval-notifications.md`.
Operazioni e deploy: `docs/cloud-run-setup.md`.

## Il percorso di una richiesta

```
Telegram ──► gateway (pubblico)      classifica ──► fuori catalogo ──► job "needs_review" (Firestore)
                                                         │
                                                         ├─► Telegram a Luigi con i bottoni + email alla lista
                                                         ▼
Luigi: Approva / Gratis / Imposta prezzo / Rifiuta    (solo il suo ID numerico, una volta sola)
                                                         ▼
gateway ──► Cloud Tasks (coda pipeline-runs, europe-west6, max-attempts=1)
                                                         ▼
pipeline-worker (privato, solo l'account pipeline-tasks)   reclama il job (approved → running)
        │   pipeline LangGraph a 6 agenti, prezzo = quello approvato
        ▼
Telegram a Luigi: il FILE + scheda (prodotto, prezzo, QA, rischio) + [Invia al cliente] [Scarta]
        ▼
Invia → il file parte al richiedente (delivering → delivered, una volta sola)     Scarta → il cliente non sa nulla
```

Stati di un job: `needs_review` → `approved` → `running` → `awaiting_review` → `delivering` → `delivered`
(oppure `rejected`, `discarded`, `failed`; una run fallita si riavvia con Riprova o `/run`).

## Cosa c'è

| Parte | File |
|-------|------|
| Avvisi a Luigi (Telegram, email) e invio del risultato | `gateway/notify.py` |
| Archivio dei job (file in locale, Firestore in produzione), `transition()` atomico | `gateway/jobstore.py` |
| Regole delle decisioni: chi, prezzi, bottoni, stati, testi | `gateway/admin.py` |
| Gestione Telegram: bottoni, comandi, consegna, Riprova | `gateway/admin_telegram.py` |
| Messa in coda (Cloud Tasks) | `gateway/pipeline_queue.py` |
| Servizio privato che esegue la pipeline (`POST /run`) | `gateway/pipeline_worker.py`, `gateway/Dockerfile.worker`, `gateway/requirements.worker.txt` |
| Esecuzione della pipeline senza interfaccia | `gateway/studio_runner.py` |
| Log dei messaggi per sessione, silenziamento dei log con il token | `gateway/convlog.py` |
| Deploy | `scripts/deploy_cloudrun.sh`, `scripts/cloudrun_lib.sh`, `deploy/cloudbuild.*.yaml` |
| Pipeline (modifiche opt-in e correzioni) | `deliverables/2026-05-25_016_aistudio-langgraph/` |

## Comandi di Luigi (solo dal suo account)

`/pending` · `/approve <id> [prezzo|gratis]` · `/prezzo <id> <prezzo>` · `/reject <id> [motivo]` ·
`/run <id>` · `/file <id>`

## Impostazioni (`.env`, copiate dallo script di deploy)

`NOTIFY_EMAILS`, `NOTIFY_TELEGRAM_CHAT_IDS` (ID numerico di Luigi), `SMTP_USER`, `SMTP_PASSWORD`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_RAG_BOT_TOKEN`, `OPENAI_API_KEY`; opzionali `PIPELINE_PROVIDER` (default `openai`),
`PIPELINE_RUN_TIMEOUT` (600 s), `TASKS_LOCATION` (default `europe-west6`), `JOB_STORE`.
Il segreto del webhook (`TELEGRAM_WEBHOOK_SECRET`) lo genera e lo registra lo script.

## Servizi (progetto `aistudio-milano`, regione `europe-west8`)

| Servizio | Accesso | URL |
|----------|---------|-----|
| `gateway` | pubblico (webhook Telegram con secret) | https://gateway-ebk76b4n7q-oc.a.run.app |
| `rag-api` | pubblico (webhook Telegram) | https://rag-api-ebk76b4n7q-oc.a.run.app |
| `pipeline-worker` | privato, solo `pipeline-tasks` | https://pipeline-worker-ebk76b4n7q-oc.a.run.app |

## Costi e limiti

- Ogni run chiama OpenAI circa 10 volte (centesimi). Parte solo ciò che Luigi approva; la coda non ripete mai una run fallita.
- Cloud Tasks, Firestore e Cloud Run restano nel free tier a questi volumi (vedi `docs/cloud-run-setup.md`, sezione 8).
- Il worker non fa `git push`, non manda email di Francesca e non scrive il registro: la registrazione di una consegna è manuale.

## Prove

`pytest tests/test_gateway_*.py tests/test_pipeline_*.py tests/test_studio_*.py tests/test_deploy_cloudrun_lib.py tests/test_token_logging.py`
(la pipeline gira con un LLM finto: nessuna rete, nessun git, nessuna scrittura nel repo).
