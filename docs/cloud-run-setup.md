# Cloud Run — setup e deploy

Stato al 2026-10-09: **`gateway` e `rag-api` online** (audit 035).
Progetto GCP `aistudio-milano`, regione `europe-west8` (Milano).

| Servizio | URL | Origine |
|----------|-----|---------|
| `gateway` | https://gateway-947977086404.europe-west8.run.app | `gateway/Dockerfile` |
| `rag-api` | https://rag-api-947977086404.europe-west8.run.app | `scripts/rag/Dockerfile` |

Console: [servizi](https://console.cloud.google.com/run?project=aistudio-milano) ·
[build](https://console.cloud.google.com/cloud-build/builds?project=aistudio-milano) ·
[log](https://console.cloud.google.com/logs/query?project=aistudio-milano)

---

## 1. DA FARE ORA (in quest'ordine)

Il codice con il log dei messaggi (PR #183) è su `main` ma **non è ancora online**. Il vecchio token del bot pipeline
è finito nei log di Cloud Run (httpx scriveva l'URL con il token) e va considerato compromesso.

Esegui i comandi dalla root del repo, con `!` davanti se li lanci da Claude Code.

1. **Revoca il token del bot pipeline.** In Telegram: @BotFather → `/revoke` → `@AIStudioMilanoBot` → copia il nuovo token.
   Mettilo in `.env` come `TELEGRAM_BOT_TOKEN=...` (il file è ignorato da git). Il bot resta muto fino al passo 3.
2. **Ricostruisci l'immagine del gateway** (circa 2 minuti):
   ```bash
   gcloud builds submit . --config deploy/cloudbuild.gateway.yaml \
     --substitutions _IMAGE=europe-west8-docker.pkg.dev/aistudio-milano/aistudio/gateway \
     --project aistudio-milano
   ```
3. **Ripubblica secret, servizi e webhook** con il nuovo token (usa l'immagine appena costruita):
   ```bash
   bash scripts/deploy_cloudrun.sh --skip-build
   ```
4. **Verifica.** Scrivi un messaggio al bot: deve rispondere. Poi:
   ```bash
   gcloud run services logs read gateway --region europe-west8 --project aistudio-milano --limit 30
   python scripts/check_telegram.py --expect-webhook pipeline
   ```
   Nei log devi vedere righe `[conv] dir=in chat=… text="…"` e `[conv] dir=out chat=…`, e **nessun** URL
   `api.telegram.org/bot<token>`. `check_telegram` deve dire "All Telegram channels healthy".

Poi, senza fretta:

- [ ] **Bloccare le richieste fraudolente.** Una richiesta illecita (es. "ricetta medica falsa", job `7dff0dd502`) oggi finisce in
      `needs_review` come un prodotto fuori catalogo, senza rifiuto esplicito. Serve una categoria `refused` nel
      classificatore (`gateway/worker.py`) con risposta di rifiuto, log dedicato e test.
- [ ] **Privacy.** I log ora contengono il testo degli utenti. Aggiungi un'informativa al messaggio `/start` e decidi la
      retention del bucket di log (default 30 giorni: Cloud Logging → Log Storage).
- [ ] **Budget alert** in Google Cloud → Fatturazione → Budget e avvisi (in `europe-west8` non c'è free tier).
- [ ] `ANTHROPIC_API_KEY` in `.env` è un segnaposto: va bene finché c'è `OPENAI_API_KEY`.
- [ ] Storage persistente per la coda (Firestore / Cloud SQL), vedi sezione 6.
- [ ] Altri servizi: WhatsApp (webhook già nel gateway, servono le credenziali Twilio), form Streamlit, dashboard trading.

---

## 1b. Notifiche a Luigi per le richieste `needs_review` (nuovo)

Quando un job va in `needs_review`, il gateway scrive a Luigi: messaggio Telegram (solo testo) e email a una lista di
indirizzi (`gateway/notify.py`, piano in `docs/plans/luigi-approval-notifications.md`). Si attiva con queste righe in
`.env` (il file non finisce su git); senza di esse non succede nulla.

```
NOTIFY_EMAILS=stekkino@hotmail.it,luigi.vinegar@gmail.com
NOTIFY_TELEGRAM_CHAT_IDS=<il tuo ID numerico Telegram>
SMTP_USER=luigi.vinegar@gmail.com
SMTP_PASSWORD=<password per app di Gmail, 16 caratteri>
```

1. **Password per app di Gmail.** Account Google → Sicurezza → Verifica in due passaggi (deve essere attiva) →
   Password per le app → crea "AI Studio gateway". Incollala in `.env` come `SMTP_PASSWORD`. Lo script la porta in
   Secret Manager; non va mai in chat né su git.
2. **Il tuo ID Telegram** è quello della riga di log `[conv] dir=in chat=<ID> text="test-id-luigi"`.
3. Ricostruisci il gateway e ridistribuisci (stessi comandi della sezione 1, passi 2-3).
4. **Prova.** Scrivi al bot una richiesta fuori catalogo (non fraudolenta). Devi ricevere il messaggio su Telegram e
   l'email (controlla lo spam di Hotmail). I log mostrano `[notify] telegram sent for job …` e `[notify] email sent …`,
   oppure `failed` con il solo tipo di errore.

Limiti noti: gli avvisi sono best-effort (un canale che fallisce non blocca l'altro né la risposta all'utente), al massimo
10 al minuto, uno per job. I bottoni Approva/Rifiuta arrivano con le Fasi 2 e 3 del piano.

## 2. Come ridistribuire (promemoria)

Quando hai cambiato il codice, scegli la riga giusta. Tutti i comandi partono dalla root del repo.

| Cosa è cambiato | Comando |
|-----------------|---------|
| **Tutto** (codice di gateway e rag-api, secret, webhook) | `bash scripts/deploy_cloudrun.sh` — la build di `rag-api` dura circa 10 minuti |
| **Solo il gateway** | build gateway (passo 2 sopra), poi `gcloud run deploy gateway --image europe-west8-docker.pkg.dev/aistudio-milano/aistudio/gateway --region europe-west8 --project aistudio-milano` |
| **Solo rag-api** | `gcloud builds submit . --config deploy/cloudbuild.ragapi.yaml --substitutions _IMAGE=europe-west8-docker.pkg.dev/aistudio-milano/aistudio/rag-api --project aistudio-milano`, poi `gcloud run deploy rag-api --image europe-west8-docker.pkg.dev/aistudio-milano/aistudio/rag-api --region europe-west8 --project aistudio-milano` |
| **Solo chiavi/token** (nuovo valore in `.env`) | `bash scripts/deploy_cloudrun.sh --skip-build` |
| **Anteprima senza modifiche** | `bash scripts/deploy_cloudrun.sh --dry-run` |

`gcloud run deploy … --image` riusa le variabili d'ambiente e i secret già configurati sul servizio.
Lo script è idempotente: i secret esistenti ricevono una nuova versione, i servizi vengono aggiornati sul posto.

Il deploy crea secret e servizi pubblici: Claude Code non può lanciarlo da solo (il sistema di permessi lo blocca),
quindi lancialo tu con `!` oppure da un terminale.

Altre regioni: `REGION=us-central1 bash scripts/deploy_cloudrun.sh` (il free tier vale solo per alcune regioni US).

### Controllo dello stato

```bash
gcloud run services list --region europe-west8 --project aistudio-milano
gcloud builds list --project aistudio-milano --limit 5
gcloud run services logs read gateway --region europe-west8 --project aistudio-milano --limit 50
```

---

## 3. Variabili d'ambiente

| Variabile | Dove | Note |
|-----------|------|------|
| `OPENAI_API_KEY` | worker, rag-api | Classificazione / RAG |
| `ANTHROPIC_API_KEY` | worker | Alternativa a OpenAI (basta una delle due) |
| `TELEGRAM_BOT_TOKEN` | gateway | Bot "pipeline" |
| `TELEGRAM_RAG_BOT_TOKEN` | rag-api | Secondo bot, token **diverso** dal primo |
| `GATEWAY_SYNC_REPLY=1` | `api.py` | Obbligatoria su Cloud Run (lo script la imposta) |
| `GATEWAY_QUEUE_DIR` | `api.py`, `worker.py` | `/tmp/queue` |
| `RAG_API_URL` | gateway | Impostata dallo script all'URL di `rag-api` |
| `NOTIFY_EMAILS`, `NOTIFY_TELEGRAM_CHAT_IDS` | `notify.py` | Destinatari degli avvisi `needs_review` (liste con virgole) |
| `SMTP_USER`, `SMTP_PASSWORD` | `notify.py` | Gmail con password per app; `SMTP_PASSWORD` è un secret. Opzionali `SMTP_HOST`, `SMTP_PORT`, `NOTIFY_FROM` |
| `OPENAI_MODEL`, `ALGO_TRADING_URL`, `TRADING_API_URL` | varie | Opzionali |

I secret (`TELEGRAM_*`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) stanno in Secret Manager, copiati da `.env` dallo script.
`.env` è ignorato da git (`*.env` in `.gitignore`).

**`GATEWAY_HMAC_SECRET` non serve.** `verify_hmac()` esiste in `gateway/middleware.py` ma nessun endpoint la chiama;
il webhook WhatsApp usa `TWILIO_AUTH_TOKEN`. Non creare il secret finché la firma delle richieste non è collegata.

---

## 4. Log dei messaggi

`gateway/convlog.py` scrive su stdout una riga per ogni messaggio, con il `chat_id` come sessione:

```
2026-10-09 10:06:54 [conv] dir=in  chat=555 text="Vorrei una landing page\ncon un menu"
2026-10-09 10:06:54 [conv] dir=out chat=555 text="Richiesta ricevuta: ..."
```

- Copre i messaggi in arrivo, le risposte (incluse `/start`, `/ask` e gli errori) e le notifiche del worker.
- Newline scritti come `\n`; il testo oltre 1000 caratteri è troncato.
- `httpx` e `httpcore` loggano solo da WARNING in su, per non scrivere l'URL con il token del bot.
- Per filtrare una sessione, in Cloud Logging cerca `chat=<id>`.
- Resta fuori `rag-api` (webhook Telegram e `/chat`): non logga ancora i messaggi.

---

## 5. Storia di questo setup

- Il repo aveva già Dockerfile, `scripts/deploy_cloudrun.sh`, `process/runbook_cloudrun.md` e `deploy/cloudbuild.*.yaml`.
- Gli account di fatturazione `…2DDB46` (1), `…03EE98` (2) e un terzo erano chiusi (`open: false`) e non collegabili.
  Si è usato `016BA2-DDA96E-2DDB46`, poi collegato a `aistudio-milano`; abilitate le API `run`, `cloudbuild`,
  `artifactregistry`, `secretmanager`.
- Regione portata da `us-central1` a `europe-west8` (PR #180).
- Deploy eseguito da Luigi con `scripts/deploy_cloudrun.sh`: build gateway 1m57s, rag-api 9m28s; `/docs` 200 su
  entrambi; webhook Telegram registrati (check_telegram: healthy). Test end-to-end riuscito (risposta
  `unknown_product` corretta per una richiesta fuori catalogo).
- Bookkeeping: audit `process/audit/2026-10-09_035_cloud-run-deploy.md`, riga 035 in `CLAUDE.md`,
  `config/accounts_registry.yaml` in stato `active`.
- Log dei messaggi per sessione e fix della perdita del token (PR #183).
- `scripts/check_telegram.py` forza UTF-8 (prima andava in errore sulle console Windows).

---

## 6. Limiti da conoscere

- Il filesystem di Cloud Run è effimero: la coda in `/tmp/queue` e ogni file SQLite spariscono a ogni riavvio, e
  `GET /status/{job_id}` risponde 404 dopo la perdita dell'istanza. Per la produzione serve Firestore, Cloud SQL o GCS.
- Cloud Run dà CPU solo durante le richieste: i bot in polling non funzionano, servono i webhook (già così).
- Le app Streamlit vogliono `--session-affinity`, `--min-instances 1` e `--server.port=$PORT`.
- Cold start: la prima richiesta dopo un'inattività è lenta, soprattutto su `rag-api`. Telegram può reinviare il
  webhook e produrre una risposta doppia. `--min-instances=1` lo evita ma costa.
- In `europe-west8` non c'è free tier: con poche decine di messaggi al giorno la spesa resta di pochi centesimi,
  ma le chiamate a OpenAI/Anthropic si pagano ovunque.

## 7. Prossimi passi possibili

1. Workflow GitHub Actions `deploy-cloudrun.yml` con Workload Identity Federation (nessuna chiave JSON), trigger su
   push a `main` con path filter per servizio.
2. Log dei messaggi anche per `rag-api`.
3. Replicare il deploy per gli altri servizi (techa, dispenser, trading dashboard, ragbot, form Streamlit, WhatsApp).
