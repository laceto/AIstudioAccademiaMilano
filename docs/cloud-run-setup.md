# Cloud Run — setup del gateway

Stato al 2026-10-09. Progetto GCP: `aistudio-milano`. Regione scelta: `europe-west8` (Milano).
Servizio previsto: `studio-gateway` (da `gateway/Dockerfile`).

## 1. Cosa abbiamo scoperto nel repo

- Dockerfile già presenti: `gateway/Dockerfile`, `gateway/Dockerfile.ragbot`, `scripts/rag/Dockerfile`,
  `deliverables/2026-05-24_013_techa-streamlit/`, `…_014_dispenser-input/`,
  `…_026_trading-agent-dashboard/`, `…_011_bakery-v2/site/`, `spaces/trading-agent-team/`.
- `gateway/Dockerfile` è già pronto per Cloud Run: ascolta su `$PORT` (default 8080) e scrive la coda in `/tmp/queue`.
- Il Dockerfile copia `config/` e `process/audit/` dalla root: il contesto di build deve essere la root del repo.
- `config/accounts_registry.yaml` elenca Cloud Run con `project_id: null` (da compilare con `aistudio-milano`).
- Nessun workflow GitHub Actions di deploy esiste ancora. L'audit `process/audit/2026-05-24_010_cloud-run-deploy.md`
  descrive un deploy fatto per un altro repo (`laceto/rss_feed`).

## 2. Cosa è stato fatto

| Passo | Esito |
|-------|-------|
| `gcloud` installato e autenticato come `luigi.vinegar@gmail.com`, progetto di default `aistudio-milano` | OK |
| Fatturazione: gli account `…2DDB46` (1), `…03EE98` (2) e un terzo erano chiusi (`open: false`) | Bloccante, poi risolto |
| Collegato l'account di fatturazione `016BA2-DDA96E-2DDB46` (ora `open: true`) a `aistudio-milano` | OK, `billingEnabled: true` |
| Abilitate le API `run`, `cloudbuild`, `artifactregistry`, `secretmanager` | OK |
| Creazione del secret `GATEWAY_HMAC_SECRET` | **Bloccata** dal sistema di permessi, non creato |
| `gcloud run deploy studio-gateway …` | **Bloccato** dal sistema di permessi, non eseguito |

Non è stato creato nessun secret e nessun servizio. Nessun valore sensibile è stato scritto in questo documento.

## 3. Variabili d'ambiente lette dal gateway

| Variabile | Dove | Note |
|-----------|------|------|
| `GATEWAY_HMAC_SECRET` | `middleware.py` | Obbligatoria per le richieste firmate (senza, la verifica HMAC fallisce) |
| `OPENAI_API_KEY` | `worker.py` | Worker |
| `ANTHROPIC_API_KEY` | `worker.py` | Worker |
| `TELEGRAM_BOT_TOKEN` | `worker.py`, `api.py` | Bot Telegram |
| `OPENAI_MODEL` | `worker.py` | Opzionale, default `gpt-4o-mini` |
| `GATEWAY_QUEUE_DIR` | `api.py`, `worker.py` | Già impostata a `/tmp/queue` nel Dockerfile |
| `ALGO_TRADING_URL`, `TRADING_API_URL`, `RAG_API_URL` | `api.py` | Opzionali, URL degli altri servizi |

I bot WhatsApp e Telegram (`bot_whatsapp.py`, `bot_telegram.py`, `rag_bot_telegram.py`) leggono altre chiavi (es. Twilio):
controlla `.env.example` prima di decidere cosa mettere in Secret Manager.

## 4. Cosa devi fare tu

Esegui questi comandi in una shell con `gcloud` (Git Bash per `openssl`). In Claude Code puoi anteporre `!`.

### 4.1 Crea i secret

```bash
# HMAC casuale, il valore non viene mostrato
openssl rand -hex 32 | gcloud secrets create GATEWAY_HMAC_SECRET \
  --project aistudio-milano --replication-policy=automatic --data-file=-

# Chiavi reali: incolla il valore quando richiesto, non scriverlo nella chat
printf "Valore OPENAI_API_KEY: "; read -rs V; echo
printf %s "$V" | gcloud secrets create OPENAI_API_KEY --project aistudio-milano --replication-policy=automatic --data-file=-
# ripeti per ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, ecc.
```

### 4.2 Dai accesso ai secret al service account di Cloud Run

```bash
PN=$(gcloud projects describe aistudio-milano --format="value(projectNumber)")
for S in GATEWAY_HMAC_SECRET OPENAI_API_KEY ANTHROPIC_API_KEY TELEGRAM_BOT_TOKEN; do
  gcloud secrets add-iam-policy-binding $S --project aistudio-milano \
    --member="serviceAccount:$PN-compute@developer.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor
done
```

### 4.3 Deploy (dalla root del repo)

```bash
gcloud run deploy studio-gateway \
  --source . --dockerfile gateway/Dockerfile \
  --region europe-west8 --project aistudio-milano \
  --min-instances 0 --max-instances 3 \
  --set-secrets GATEWAY_HMAC_SECRET=GATEWAY_HMAC_SECRET:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest \
  --allow-unauthenticated
```

- `--allow-unauthenticated` rende il servizio pubblico. Per un primo test privato toglilo e chiama il servizio con un token IAM
  (`curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" …`). I webhook di Telegram/WhatsApp richiedono però l'accesso pubblico.
- Se `--dockerfile` non è accettato, aggiorna gcloud (`gcloud components update`) oppure costruisci con
  `gcloud builds submit --tag europe-west8-docker.pkg.dev/aistudio-milano/<repo>/gateway -f gateway/Dockerfile .`.
- Se il deploy chiede di creare il repository Artifact Registry, accetta.

### 4.4 Verifica

```bash
URL=$(gcloud run services describe studio-gateway --region europe-west8 --project aistudio-milano --format="value(status.url)")
curl "$URL/docs"     # pagina Swagger di FastAPI
gcloud run services logs read studio-gateway --region europe-west8 --project aistudio-milano --limit 50
```

### 4.5 Dopo il deploy

- Aggiorna i webhook Telegram e Twilio con il nuovo URL `*.run.app`.
- Compila `project_id: aistudio-milano` in `config/accounts_registry.yaml`.
- Crea l'audit log in `process/audit/` e aggiungi la riga in "Delivered Requests" di `CLAUDE.md` (prodotto interno, 0.00).
- Imposta un budget alert in Google Cloud → Fatturazione → Budget e avvisi.

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
