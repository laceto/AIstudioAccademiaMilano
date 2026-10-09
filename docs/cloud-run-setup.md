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
- [ ] **Collegare il gateway alla pipeline.** I job `classified`/approvati non avviano nessun lavoro (il bot dice "in lavorazione"
      ma non succede nulla). Fase 5 di `docs/plans/luigi-approval-notifications.md`.
- [ ] **Privacy.** I log ora contengono il testo degli utenti. Aggiungi un'informativa al messaggio `/start` e decidi la
      retention del bucket di log (default 30 giorni: Cloud Logging → Log Storage).
- [ ] **Budget alert** in Google Cloud → Fatturazione → Budget e avvisi (es. 5 €): è la rete di sicurezza, vedi sezione 8.
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

## 1e. Dalla tua approvazione al file finito (Fase 5, nuovo)

Quando approvi un job (Approva, Gratis o Imposta prezzo) la pipeline a 6 agenti parte da sola:

1. Il gateway mette il job in una coda Cloud Tasks (`pipeline-runs`) e ti scrive "Pipeline avviata per il job ...".
2. La coda chiama il servizio **`pipeline-worker`**, che è **privato**: lo può chiamare solo l'account di servizio
   `pipeline-tasks`, quindi nessuno può far partire una run (a pagamento) conoscendo l'URL.
3. Il worker reclama il job con un cambio di stato atomico (`approved` -> `running`), esegue la pipeline e salva il
   risultato (`awaiting_review`). Un secondo avvio dello stesso job viene saltato senza spendere LLM.
4. Ti arriva su Telegram il **file** con la scheda (prodotto, prezzo, QA, rischio) e i bottoni **Invia al cliente / Scarta**.
   Se la run fallisce, ricevi il motivo e il bottone **Riprova** (oppure `/run <job_id>`).

5. **Invia al cliente**: il file parte dal bot verso chi l'ha chiesto, con un testo senza dettagli interni (niente esito QA né
   punteggio di rischio): prezzo, numero di fattura e Job ID. **Scarta**: non parte nulla e il cliente non viene avvisato.
6. L'invio avviene **una volta sola** (il risultato viene prima "preso in carico", poi inviato). Se Telegram rifiuta (il
   cliente ha bloccato il bot) il risultato torna in attesa, tu vieni avvisato e puoi riprovare con lo stesso bottone.

Il cliente non riceve nulla finché non premi Invia. Se il cliente non è su Telegram (canale API o WhatsApp) l'invio
automatico non c'è: il bot te lo dice e il file lo giri tu a mano.

Stati di un job: `needs_review` -> `approved` -> `running` -> `awaiting_review` -> `delivering` -> `delivered`
(oppure `discarded`; una run andata male passa da `failed` e si riavvia con Riprova o `/run`).

**Per attivarlo** (è il primo deploy che crea la coda, l'account di servizio e il worker):

```
bash scripts/deploy_cloudrun.sh --build=gateway,worker
```

`--build=` ricostruisce solo le immagini indicate (la build di `rag-api` dura circa 10 minuti e qui non serve).
Prima prova: `bash scripts/deploy_cloudrun.sh --dry-run --build=gateway,worker`. Lo script abilita l'API Cloud Tasks,
crea `pipeline-tasks` e la coda con `max-attempts=1` (una run fallita non si ripete da sola), distribuisce il worker e
passa al gateway coda, URL del worker e account di servizio. La prima volta i permessi possono impiegare qualche
minuto a propagarsi: se la prima run non parte, `/run <job_id>` la rimette in coda.

**Regione della coda.** Cloud Tasks non esiste a Milano (`europe-west8` dà "not a valid location"): la coda sta a Zurigo
(`europe-west6`, la regione supportata più vicina; cambia con `TASKS_LOCATION=...`). Nella coda viaggia solo il Job ID,
nessun dato personale, quindi non conta che stia in una regione diversa dai servizi. Elenco: `gcloud tasks locations list`.

**Costi.** Ogni run chiama OpenAI circa 10 volte (qualche centesimo). Parte solo ciò che approvi tu, quindi nessuno
sconosciuto può farti spendere. Cloud Tasks è gratuito fino a 1 milione di operazioni al mese; il worker scala a zero.

**Cosa non fa dal cloud:** niente `git push`, niente email Gmail di Francesca, niente scritture nel repo né audit log
automatico. Il risultato sta sul job in Firestore (`result`) e nel messaggio a te. Il registro in `process/audit/`
resta manuale.

**Prezzo.** La pipeline fattura al prezzo che hai approvato (anche gratis), non al listino.

### Cosa succede a un job fermo in `running`

Se il worker crasha, viene ucciso o Cloud Run taglia la richiesta a 900 s, il job resterebbe `running` per sempre.
Un job è **fermo** quando è `running` da più di `PIPELINE_STALE_SECONDS` (default 1200 = 900 s più margine; conta da
`started_at`, altrimenti da `created_at`). Lo "sweep" lo porta a `failed` con "Interrotta: il worker non ha finito, job
fermo da N minuti" (transizione atomica `running -> failed`: un job che finisce nello stesso istante non viene toccato),
registra `swept_at` e ti manda **una sola volta** il messaggio di errore con il bottone Riprova. **Non rilancia mai nulla**
(costa e la prima run potrebbe essere ancora viva): ripartire è una tua scelta (Riprova o `/run <job_id>`).

Chi lancia lo sweep:
- **Cloud Scheduler**, ogni 10 minuti: job `sweep-stuck-jobs` che fa `POST <url worker>/sweep` con token OIDC come
  `pipeline-tasks@<progetto>.iam.gserviceaccount.com` (audience = URL del worker; stessa identità e stesso `run.invoker`
  di Cloud Tasks). Lo crea o aggiorna `deploy_cloudrun.sh` (abilita `cloudscheduler.googleapis.com`). Gratuito per i primi
  3 job per account di fatturazione. Anche Scheduler potrebbe non supportare Milano: la sede è `SCHEDULER_LOCATION`
  (default `europe-west6`); verifica con `gcloud scheduler locations list`. Sposta solo il trigger, non i dati.
- **`/sweep` su Telegram** (solo tu; per gli altri "Comando non disponibile"): lo stesso controllo, subito.
- **`/pending`** elenca anche i job `running` con l'età e segna **FERMO?** quelli oltre la soglia.

**Risultato in ritardo.** Se la run originale finisce dopo lo sweep, il suo risultato (già pagato) non va perso: il worker
lo salva (`failed -> awaiting_review`, `late_result: true`) e ti manda il file con Invia / Scarta, ma solo se il job è
ancora `failed` per mano dello sweep e `started_at` è quello della sua run. Se nel frattempo hai premuto Riprova il
risultato vecchio viene scartato, così non sovrascrive la run nuova. Una run che fallisce dopo lo sweep non ti riscrive.

## 1d. Approvare le richieste da Telegram (nuovo)

Quando arriva una richiesta fuori catalogo ricevi il messaggio con quattro bottoni: **Approva EUR x** (solo se esiste un
prezzo a catalogo), **Gratis**, **Imposta prezzo**, **Rifiuta**. Comandi equivalenti, solo dal tuo account:

| Comando | Cosa fa |
|---------|---------|
| `/run <job_id>` | rimette in coda la pipeline per un job approvato o fallito |
| `/file <job_id>` | ti rimanda il file di un risultato in attesa di revisione (se il messaggio si è perso) |
| `/pending` | elenca richieste da approvare, risultati da rivedere e run fallite, ciascuna con i suoi bottoni |
| `/approve <job_id> [prezzo\|gratis]` | approva; senza prezzo usa quello a catalogo |
| `/prezzo <job_id> <prezzo>` | approva a un prezzo che scegli (es. `12,50`) |
| `/reject <job_id> [motivo]` | rifiuta; il motivo resta interno |
| `/cancella <job_id>` o `/cancella chat <chat_id>` | cancellazione su richiesta del cliente: mostra una scheda (numero di job, stati, date, mai il testo) con Conferma / Annulla; solo Conferma cancella. Vedi sezione 4b |

La persona che ha fatto la richiesta riceve l'esito. Una decisione si applica una volta sola.

**Sicurezza.** Il gateway ti riconosce dall'ID numerico, e quell'ID sta nel messaggio che Telegram invia al webhook:
senza controllo sarebbe falsificabile. Per questo il deploy genera `TELEGRAM_WEBHOOK_SECRET` (in Secret Manager), lo passa al
gateway e lo registra su Telegram con `setWebhook`. Il gateway rifiuta con 403 ogni richiesta che non lo porta. Se il segreto
manca, i bottoni e i comandi restano spenti ma gli utenti normali sono serviti.

**Per attivarlo:** ricostruisci il gateway e lancia `bash scripts/deploy_cloudrun.sh --skip-build` (sezione 1, passi 2-3).
Poi scrivi al bot una richiesta fuori catalogo, premi un bottone e controlla che l'utente riceva l'esito.
Verifica rapida del segreto: `curl -s -o /dev/null -w "%{http_code}" -X POST <url-gateway>/webhook/telegram -d "{}"` deve
rispondere `403`.

## 1c. Job su Firestore (nuovo)

I job non sono più file in `/tmp/queue`: `gateway/jobstore.py` li salva in Firestore (`JOB_STORE=firestore`, collezione
`jobs`), quindi sopravvivono ai riavvii e `GET /status/{job_id}` non risponde più 404 dopo un riavvio. In locale e nei test
resta il backend a file (nessuna variabile necessaria).

**Per attivarlo** basta ricostruire il gateway e rilanciare lo script (gli stessi passi della sezione 1, punti 2-3):
`bash scripts/deploy_cloudrun.sh --skip-build` ora anche abilita l'API Firestore, crea il database `(default)` in
`europe-west8` (modalità Firestore nativa, la località non si cambia più), assegna a Cloud Run il ruolo
`roles/datastore.user` e imposta `JOB_STORE=firestore` sul gateway.

Dopo il deploy: scrivi al bot una richiesta qualsiasi, poi controlla in
[Firestore](https://console.cloud.google.com/firestore/databases/-default-/data/panel/jobs?project=aistudio-milano) che
compaia il documento `jobs/<job_id>`, e che `GET <url-gateway>/status/<job_id>` risponda anche dopo un riavvio.

Il backend Firestore è testato con un client finto, non contro Firestore vero: la prima prova reale è questo deploy.

**Retention dei job (TTL) e protezione dalla cancellazione.** Ogni documento contiene il testo dell'utente, quindi non
resta per sempre:

- Ogni nuovo job nasce con `expire_at` = data di creazione + `JOB_RETENTION_DAYS` (90 giorni se non impostato; vedi
  `gateway/retention.py`). Nel codice è una stringa ISO-8601; `FirestoreJobStore` la salva come *timestamp* UTC, perché
  il TTL di Firestore legge solo campi di tipo timestamp. La scadenza conta dalla creazione: cambiare lo stato del job
  (approvato, consegnato...) **non** la sposta.
- Il deploy (`scripts/deploy_cloudrun.sh`) crea il criterio TTL sul campo `expire_at` del gruppo di collezioni `jobs`
  e attiva la protezione dalla cancellazione del database `(default)`. Entrambi i passi controllano prima lo stato e
  non fanno nulla se è già a posto. Con `--dry-run` vengono solo elencati.
- Firestore cancella i documenti scaduti in background, **di solito entro circa 24 ore** dalla scadenza (non è
  istantaneo: un job scaduto può restare leggibile per un giorno). Le cancellazioni TTL si pagano come normali
  cancellazioni di documenti.
- **Controllare il criterio:** console Firestore, [Time to live](https://console.cloud.google.com/firestore/databases/-default-/ttl?project=aistudio-milano):
  deve esserci `jobs` / `expire_at` con stato *Serving* (subito dopo la creazione può essere *Creating*). Da riga di
  comando: `gcloud firestore fields ttls list --collection-group=jobs --database='(default)'`.
- **Attenzione: un job ancora in sospeso al giorno N viene cancellato al giorno N.** La scadenza conta dalla
  creazione, non dall'ultima attività: una richiesta rimasta in `needs_review` (o `approved`, `running`...) oltre il
  periodo di retention sparisce comunque. Se serve più tempo per agire, alza `JOB_RETENTION_DAYS`: il numero (e
  quello dell'informativa privacy) viene solo da `gateway/retention.py`, non va scritto altrove.
- **Job creati prima del TTL** non hanno `expire_at` e non scadrebbero mai. Si sistemano una volta, con lo script
  (prima senza `--apply`: è una prova a vuoto che stampa solo i conteggi per stato, mai il testo dei clienti):
  `python -m scripts.backfill_job_expiry`, poi `python -m scripts.backfill_job_expiry --apply`
  (con `JOB_STORE=firestore FIRESTORE_PROJECT=aistudio-milano`). Due regole:
  - job **conclusi** (`delivered`, `discarded`, `rejected`, `classified`): creazione + retention; quelli già più vecchi
    del periodo vengono cancellati dal TTL entro circa 24 ore dall'`--apply`;
  - job **in sospeso** (ogni altro stato, compresi quelli che lo script non conosce): oggi + retention, un periodo
    intero nuovo, così Luigi fa in tempo ad agire. Dopo quel periodo valgono le stesse regole di tutti gli altri.
- **Protezione dalla cancellazione:** finché è attiva, il database non si può cancellare (né da comando né dalla
  console). Per cancellarlo di proposito va prima spenta, in modo volontario:
  `gcloud firestore databases update --database='(default)' --no-delete-protection`
  (oppure console Firestore, Impostazioni database, Protezione dalla cancellazione). Un nuovo `deploy_cloudrun.sh` la
  riaccende. Non cancellare il database per "ripartire da zero" senza prima aver esportato ciò che serve.

## 2. Come ridistribuire (promemoria)

Quando hai cambiato il codice, scegli la riga giusta. Tutti i comandi partono dalla root del repo.

| Cosa è cambiato | Comando |
|-----------------|---------|
| **Tutto** (codice di gateway e rag-api, secret, webhook) | `bash scripts/deploy_cloudrun.sh` — la build di `rag-api` dura circa 10 minuti |
| **Solo il worker della pipeline** | `bash scripts/deploy_cloudrun.sh --build=worker` |
| **Solo il gateway** | build gateway (passo 2 sopra), poi `gcloud run deploy gateway --image europe-west8-docker.pkg.dev/aistudio-milano/aistudio/gateway --region europe-west8 --project aistudio-milano` |
| **Solo rag-api** | `gcloud builds submit . --config deploy/cloudbuild.ragapi.yaml --substitutions _IMAGE=europe-west8-docker.pkg.dev/aistudio-milano/aistudio/rag-api --project aistudio-milano`, poi `gcloud run deploy rag-api --image europe-west8-docker.pkg.dev/aistudio-milano/aistudio/rag-api --region europe-west8 --project aistudio-milano` |
| **Solo chiavi/token** (nuovo valore in `.env`) | `bash scripts/deploy_cloudrun.sh --skip-build` |
| **Anteprima senza modifiche** | `bash scripts/deploy_cloudrun.sh --dry-run` |

`gcloud run deploy … --image` riusa le variabili d'ambiente e i secret già configurati sul servizio.
Lo script è idempotente: i secret esistenti ricevono una nuova versione, i servizi vengono aggiornati sul posto.

Il deploy crea secret e servizi pubblici: Claude Code non può lanciarlo da solo (il sistema di permessi lo blocca),
quindi lancialo tu con `!` oppure da un terminale.

Altre regioni: `REGION=us-central1 bash scripts/deploy_cloudrun.sh`. Non serve per il free tier (vedi sezione 8); attenzione che il database Firestore, una volta creato, resta nella sua località.

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
| `PIPELINE_STALE_SECONDS` | worker, gateway | Dopo quanti secondi in `running` un job è fermo (default 1200). Vedi "Cosa succede a un job fermo" |
| `SCHEDULER_LOCATION` | `deploy_cloudrun.sh` | Sede del job Cloud Scheduler `sweep-stuck-jobs` (default `europe-west6`) |
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

## 4b. Informativa privacy del bot (nuovo)

`gateway/privacy.py` contiene il testo. `/start` risponde con il benvenuto di sempre più un paragrafo breve che rimanda
a `/privacy`; `/privacy` manda l'informativa completa (art. 13 GDPR, in italiano semplice) e **non crea mai un job**.
Non chiede consenso: è solo informazione. I numeri non sono scritti nel testo: i giorni di conservazione dei job vengono da
`retention_days()` (`JOB_RETENTION_DAYS`, default 90), i caratteri registrati da `convlog.MAX_CHARS`.

Ai clienti si dice: quali dati si conservano (testo, ID Telegram/chat, classificazione, risultato delle richieste
approvate), perché, che Luigi rivede ogni richiesta fuori catalogo (Telegram + e-mail via Gmail), i fornitori (Google Cloud:
Cloud Run e Firestore a `europe-west8`, Cloud Logging, Cloud Tasks a `europe-west6`; OpenAI; Telegram; Gmail), la
conservazione (job: `retention_days()` giorni; righe di log: 30 giorni di default), i diritti e il reclamo al Garante.

**Contatto.** Imposta `PRIVACY_CONTACT` in `.env` (un indirizzo e-mail o un `@handle`); `deploy_cloudrun.sh` lo passa al
gateway come le `NOTIFY_*`. Se manca, l'informativa dice onestamente che non c'è un indirizzo dedicato e di scrivere nella chat.

**Da confermare tu (Luigi), non è consulenza legale:**
1. identità del titolare (nome o ragione sociale, P.IVA/CF, indirizzo): il testo nomina solo il marchio e Milano;
2. l'indirizzo in `PRIVACY_CONTACT`;
3. la base giuridica (art. 6, par. 1, lett. b);
4. i trasferimenti fuori UE (OpenAI, Telegram, Google): il testo ne parla in generale;
5. se citare Anthropic: `gateway/worker.py` lo usa se `ANTHROPIC_API_KEY` è impostata, il testo cita solo OpenAI;
6. `LOG_RETENTION_DAYS` (30) in `gateway/privacy.py` è il default di Cloud Logging: se cambi la retention del bucket, cambia la costante.

**Cancellazione su richiesta (`/cancella`, nuovo).** Il percorso principale e' `/cancella chat <chat_id>` o
`/cancella <job_id>` su Telegram (solo tu; gli altri ricevono "Comando non disponibile"), passo per passo in
`process/runbook_privacy_requests.md`. Il comando non cancella: mostra la scheda e cancella solo su Conferma.
Non cancella mai job in `running` o `delivering` (lo stato e' riletto al momento della cancellazione): aspetta o usa `/sweep`.
Dopo la cancellazione ti elenca cio' che devi fare a mano: copie e-mail, messaggi/file nella tua chat, righe `[conv]` nei log
(scadono da sole dopo 30 giorni). I passi in console Firestore restano come ripiego.
Codice: `gateway/erasure.py`, `JobStore.delete()`, test in `tests/test_gateway_erasure.py`.

**Registro delle cancellazioni (`erasures`).** Ogni cancellazione che ha rimosso qualcosa scrive un documento nella collezione
Firestore `erasures` (file `gateway/erasures/` in locale; stesso backend di `JOB_STORE`; `ERASURES_COLLECTION` e `ERASURE_DIR`
per cambiare nome/cartella): ora, ID admin, `job`/`chat`, numero e ID dei job (casuali). Niente ID di chat, testo o risultato.
Serve il ruolo `roles/datastore.user` che il servizio ha gia' per `jobs`. **Decisione per Luigi:** il registro non ha TTL, cosi'
puoi dimostrare di aver cancellato; contiene solo ID casuali e il tuo ID. Se preferisci una scadenza, aggiungi una policy TTL
su un campo timestamp (oggi `at` e' testo ISO: andrebbe salvato come timestamp). Non l'ho attivata.
Limite: lo stato e' riletto subito prima di ogni cancellazione, ma lettura e cancellazione non sono una sola operazione atomica.

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
- I costi di hosting a questi volumi restano nel free tier (sezione 8); le chiamate a OpenAI/Anthropic si pagano ovunque.

## 8. Regione e costi (verificato il 2026-10-09)

**Europa o USA: per il free tier non cambia.** Lo avevamo scritto al contrario (il runbook diceva che il free tier valeva solo
per regioni US): non è supportato dalla documentazione attuale.

- `europe-west8` (Milano) è nell'elenco "Tier 1" delle regioni Cloud Run
  ([Cloud Run locations](https://docs.cloud.google.com/run/docs/locations)).
- La tabella [Always Free](https://docs.cloud.google.com/free/docs/free-cloud-features) non indica restrizioni di regione
  per queste righe:

| Servizio | Gratis ogni mese (Firestore: ogni giorno) | Come lo usiamo |
|----------|-------------------------------------------|----------------|
| Cloud Run | 2 milioni di richieste, 360.000 GB-secondi, 180.000 vCPU-secondi | scala a zero (`--min-instances 0`): nessun costo da fermo |
| Firestore | 1 GiB, 50.000 letture, 20.000 scritture, 20.000 cancellazioni al giorno, per progetto | poche decine di job al giorno |
| Secret Manager | 6 versioni attive, 10.000 accessi | vedi sotto |
| Cloud Build | 2.500 minuti `e2-standard-2` | build da 2 e 10 minuti |
| Artifact Registry | 0,5 GB | vedi sotto |

L'unico limite legato a un continente è il traffico in uscita di Cloud Run: 1 GB al mese "from North America".

**Cosa può costare comunque, in centesimi**
- **Secret Manager:** fino al 2026-10-09 lo script aggiungeva una nuova versione dei secret a ogni deploy (oggi i secret
  sono alla versione 4-5); sopra le 6 versioni attive si paga circa 0,06 $ per versione al mese. Ora la aggiunge solo se il
  valore è cambiato (`upsert_secret` in `scripts/cloudrun_lib.sh`). Restano le versioni vecchie: distruggile con
  `gcloud secrets versions destroy <n> --secret=<NOME>` (tieni l'ultima).
- **Artifact Registry:** il repository pesa già circa 257 MB e cresce a ogni build; oltre 0,5 GB si pagano pochi
  centesimi al mese. Rimedio: un criterio di pulizia che tiene le ultime 2-3 immagini.
- **Traffico in uscita** oltre il gratuito, e `--min-instances 1` (non lo usiamo).
- **OpenAI/Anthropic e SMTP di Gmail:** le API LLM si pagano a parte; Gmail è gratuito.
- Sono prezzi della pagina ufficiale al momento della verifica: non ho potuto leggere la nota sul free tier nella pagina
  dei prezzi di Cloud Run (la pagina si tronca), quindi **controlla il primo mese in Fatturazione → Report**.

**Decisione già presa e non reversibile:** la località di Firestore. Lo script la crea uguale a `REGION`
(`europe-west8`), che è la regione giusta per dati di utenti italiani/UE. Non cambiarla in `us-central1` per "risparmiare":
non risparmia nulla e sposterebbe i dati degli utenti fuori dall'UE.

## 7. Prossimi passi possibili

1. Workflow GitHub Actions `deploy-cloudrun.yml` con Workload Identity Federation (nessuna chiave JSON), trigger su
   push a `main` con path filter per servizio.
2. Log dei messaggi anche per `rag-api`.
3. Replicare il deploy per gli altri servizi (techa, dispenser, trading dashboard, ragbot, form Streamlit, WhatsApp).
