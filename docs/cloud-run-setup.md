# Cloud Run — setup del gateway

Stato al 2026-10-09. Progetto GCP: `aistudio-milano`. Regione scelta: `europe-west8` (Milano).
Servizi: `gateway` e `rag-api`, distribuiti da `scripts/deploy_cloudrun.sh`.

## 1. Cosa abbiamo scoperto nel repo

- Dockerfile già presenti: `gateway/Dockerfile`, `gateway/Dockerfile.ragbot`, `scripts/rag/Dockerfile`,
  `deliverables/2026-05-24_013_techa-streamlit/`, `…_014_dispenser-input/`,
  `…_026_trading-agent-dashboard/`, `…_011_bakery-v2/site/`, `spaces/trading-agent-team/`.
- `gateway/Dockerfile` è già pronto per Cloud Run: ascolta su `$PORT` (default 8080) e scrive la coda in `/tmp/queue`.
- Il Dockerfile copia `config/` e `process/audit/` dalla root: il contesto di build deve essere la root del repo.
- `config/accounts_registry.yaml` elenca Cloud Run con `project_id: null` (da compilare con `aistudio-milano`).
- Esistono `scripts/deploy_cloudrun.sh`, `process/runbook_cloudrun.md` e `deploy/cloudbuild.*.yaml`.
- Nessun workflow GitHub Actions di deploy esiste ancora. L'audit `process/audit/2026-05-24_010_cloud-run-deploy.md`
  descrive un deploy fatto per un altro repo (`laceto/rss_feed`).

## 2. Cosa è stato fatto

| Passo | Esito |
|-------|-------|
| `gcloud` installato e autenticato come `luigi.vinegar@gmail.com`, progetto di default `aistudio-milano` | OK |
| Fatturazione: gli account `…2DDB46` (1), `…03EE98` (2) e un terzo erano chiusi (`open: false`) | Bloccante, poi risolto |
| Collegato l'account di fatturazione `016BA2-DDA96E-2DDB46` (ora `open: true`) a `aistudio-milano` | OK, `billingEnabled: true` |
| Abilitate le API `run`, `cloudbuild`, `artifactregistry`, `secretmanager` | OK |
| Creazione del secret `GATEWAY_HMAC_SECRET` | Bloccata dai permessi; poi risulta non necessaria (vedi sezione 3) |
| `gcloud run deploy studio-gateway …` | Bloccato dai permessi; sostituito da `scripts/deploy_cloudrun.sh` |

Non è stato creato nessun secret e nessun servizio. Nessun valore sensibile è stato scritto in questo documento.

## 3. Variabili d'ambiente del gateway

| Variabile | Dove | Note |
|-----------|------|------|
| `OPENAI_API_KEY` | `worker.py` | Classificazione / RAG |
| `ANTHROPIC_API_KEY` | `worker.py` | Alternativa a OpenAI (basta una delle due) |
| `TELEGRAM_BOT_TOKEN` | `worker.py`, `api.py` | Bot "pipeline" |
| `TELEGRAM_RAG_BOT_TOKEN` | rag-api | Secondo bot, token **diverso** dal primo |
| `GATEWAY_SYNC_REPLY=1` | `api.py` | Obbligatoria su Cloud Run (lo script la imposta) |
| `GATEWAY_QUEUE_DIR` | `api.py`, `worker.py` | `/tmp/queue` |
| `OPENAI_MODEL`, `ALGO_TRADING_URL`, `TRADING_API_URL`, `RAG_API_URL` | varie | Opzionali |

**`GATEWAY_HMAC_SECRET` non serve ora.** `verify_hmac()` esiste in `gateway/middleware.py` ma nessun endpoint la chiama;
il webhook WhatsApp usa `TWILIO_AUTH_TOKEN`. Non creare questo secret finché la firma delle richieste non viene collegata.

## 4. Cosa devi fare tu

Esiste già uno script che fa tutto: `scripts/deploy_cloudrun.sh` (vedi `process/runbook_cloudrun.md`).
Abilita le API, crea il repository immagini, copia i secret da `.env` a Secret Manager, costruisce e distribuisce
`gateway` e `rag-api`, registra i webhook Telegram e verifica. I comandi manuali di una versione precedente di questo
documento (secret, deploy con `--source`) non servono più.

Verificato con `--dry-run` il 2026-10-09 (nulla modificato): progetto `aistudio-milano`, regione `us-central1`.

### 4.1 Prima di lanciarlo

1. In `.env` devono esserci **due token Telegram diversi**: `TELEGRAM_BOT_TOKEN` e `TELEGRAM_RAG_BOT_TOKEN`
   (secondo bot da @BotFather). Il dry-run li trova entrambi.
2. `OPENAI_API_KEY` è presente. `ANTHROPIC_API_KEY` in `.env` è ancora un segnaposto: lo script lo salta, va bene
   perché basta una delle due chiavi.
3. Regione: il default è `us-central1` (free tier). Per Milano: `REGION=europe-west8 ./scripts/deploy_cloudrun.sh`,
   ma potresti uscire dal free tier.
4. Verifica che `.env` sia ignorato da git (`git check-ignore .env`).

### 4.2 Lancio

```bash
./scripts/deploy_cloudrun.sh --dry-run   # anteprima, nessuna modifica
./scripts/deploy_cloudrun.sh             # deploy vero
./scripts/deploy_cloudrun.sh --skip-build   # ridistribuisce senza ricostruire le immagini
```

Il deploy vero crea secret nel Secret Manager e servizi pubblici: per questo non l'ho lanciato io. Usa `!` davanti
al comando per eseguirlo in questa sessione. Lo script è idempotente.

### 4.3 Verifica

- Scrivi al bot pipeline: "Ho bisogno di una landing page per il mio ristorante". Deve arrivare **una** risposta con
  il prodotto e 9.90 EUR. Se arriva solo un Job ID, `GATEWAY_SYNC_REPLY` non è arrivata al container.
- Log: `gcloud run services logs read gateway --region us-central1 --limit 50`

### 4.4 Dopo il deploy

- Compila `project_id: aistudio-milano` in `config/accounts_registry.yaml`.
- Audit log in `process/audit/` e riga in "Delivered Requests" di `CLAUDE.md`.
- Imposta un budget alert in Google Cloud, Fatturazione.

## 5. Limiti da conoscere

- Il filesystem di Cloud Run è effimero: la coda in `/tmp/queue` e ogni file SQLite sparisce a ogni riavvio.
  Per la produzione serve uno storage persistente (Firestore, Cloud SQL o un bucket GCS).
- Cloud Run dà CPU solo durante le richieste. Per bot in polling o worker in background serve `--no-cpu-throttling`
  (oppure passare ai webhook).
- Le app Streamlit vogliono `--session-affinity`, `--min-instances 1` e `--server.port=$PORT`.

## 6. Prossimi passi possibili

1. Workflow GitHub Actions `deploy-cloudrun.yml` con Workload Identity Federation (nessuna chiave JSON),
   trigger su push a `main` con path filter per servizio.
2. Script locale `scripts/deploy_cloudrun.sh` e un file di configurazione per servizio (nome, Dockerfile, secret, flag).
3. Replicare il deploy per gli altri servizi (techa, dispenser, trading dashboard, ragbot).
