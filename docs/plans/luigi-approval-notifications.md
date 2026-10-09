# Piano — notifica e approvazione di Luigi per le richieste `needs_review`

Stato: **Fasi 1, 2 e 3 attive; Fase 5 completa nel codice** (3 PR: pipeline senza interfaccia, esecuzione asincrona, consegna al cliente), da attivare con il deploy; Fase 4 (blocco richieste fraudolente) da fare. Storage: **Firestore**.
Contesto: `docs/cloud-run-setup.md`, `gateway/worker.py` (`_build_reply`), `gateway/api.py` (`/webhook/telegram`).

## 1. Problema

Quando il classificatore mette un job in `needs_review`, il gateway scrive un file JSON in `/tmp/queue`
(effimero su Cloud Run) e dice all'utente "serve l'approvazione di Luigi". **Nessuno avvisa Luigi e non esiste un
modo per approvare**: l'unica traccia è una riga nei log di Cloud Run. Lo stesso vale per i job `classified`
("in lavorazione"): nessuna pipeline parte.

## 2. Obiettivo

1. **Notificare** Luigi ogni volta che un job richiede revisione, su più canali:
   - un messaggio Telegram all'utente `@acetoluigi`;
   - un'email a una **lista di indirizzi** (primo: `stekkino@hotmail.it`).
2. **Permettere l'approvazione** (approva con prezzo / rifiuta) da Telegram, e avvisare l'utente della decisione.
3. Non perdere i job se l'istanza si riavvia.

## 3. Vincoli tecnici da conoscere

| Vincolo | Conseguenza |
|---------|-------------|
| Un bot Telegram **non può scrivere a un `@username` privato**: `sendMessage` vuole l'ID numerico, e solo dopo che l'utente ha premuto Start sul bot | `@acetoluigi` ha già scritto al bot; il suo `chat_id` numerico è stato letto dai log (sessione `[conv] dir=in chat=… text="test-id-luigi"`) e va in `.env` |
| Cloud Run ha filesystem effimero | L'approvazione richiede uno storage persistente (Firestore consigliato) |
| Cloud Run blocca la porta 25 in uscita; 465/587 sono ok | Email via SMTP submission (587) o API HTTP |
| Hotmail/Outlook tende a mettere in spam i mittenti nuovi | Mittente con SPF/DKIM validi (Gmail o dominio verificato); testare la cartella spam |
| I client email (Outlook SafeLinks) aprono in automatico i link `GET` | Un link email non deve approvare con un semplice GET: serve una pagina di conferma con POST |
| Il testo dell'utente finisce in un messaggio a Luigi | Va escluso il Markdown/HTML iniettato: niente `parse_mode` sul testo utente, oppure escape |

## 4. Decisioni

**Prese**

| Tema | Decisione |
|------|-----------|
| Email | Trasporto **SMTP di Gmail**, mittente `luigi.vinegar@gmail.com` con password per app in Secret Manager. Destinatari: lista di indirizzi (primo `stekkino@hotmail.it`) |
| Telegram | Messaggio a Luigi (`@acetoluigi`) con i bottoni **Approva / Rifiuta / Imposta prezzo** |
| Chi approva | **Solo Luigi**, autorizzato dall'**ID numerico** Telegram (non dallo username) |
| Altri utenti | Anche se scrivono al bot (ci sono altre sessioni, ad es. un secondo account ha provato richieste di test), nessun altro ID viene mai autorizzato |
| Storage dei job | **Firestore**, regione `europe-west8` (Fase 2) |

## 5. Configurazione

Gli indirizzi non vanno nel codice. Variabili d'ambiente del servizio `gateway`, lette da `.env` dallo script di deploy:

```
NOTIFY_EMAILS=stekkino@hotmail.it            # lista separata da virgole
NOTIFY_TELEGRAM_CHAT_IDS=<ID numerico di Luigi>   # solo in .env, mai su git; unico ID autorizzato ad approvare
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=luigi.vinegar@gmail.com
SMTP_PASSWORD=...                            # SECRET in Secret Manager, mai in chiaro
NOTIFY_FROM="AI Studio Milano <luigi.vinegar@gmail.com>"
```

Aggiunte allo script: `NOTIFY_*` come variabili, `SMTP_PASSWORD` come secret.

## 6. Architettura

```
Telegram ─► /webhook/telegram ─► classifica ─► needs_review ─► JobStore (Firestore)
                                                    │
                                                    └─► notify.notify_review(job)
                                                           ├─► Telegram: tutti i chat_id admin  (bottoni Approva / Rifiuta)
                                                           └─► Email:    tutti gli indirizzi    (testo + link di conferma)

Luigi preme [Approva €X] ─► callback_query ─► controlla chat_id admin ─► JobStore.update ─► avvisa l'utente
Luigi apre il link email  ─► GET /admin/job/<id>?sig=…  (pagina di conferma) ─► POST /admin/job/<id>/approve
```

Moduli nuovi:
- `gateway/notify.py` — `notify_review(job)`: invia su tutti i canali, ogni canale isolato (un errore non blocca gli altri),
  log di esito per canale, niente testo utente non scappato.
- `gateway/jobstore.py` — interfaccia `JobStore` (put, get, list_by_status; l'aggiornamento transazionale arriva in Fase 3) con implementazione file
  (test e locale) e Firestore (produzione).
- `gateway/admin.py` — autorizzazione (`is_admin(chat_id)`), firma dei link email (HMAC-SHA256, scadenza),
  rotte `/admin/job/...`. Qui `GATEWAY_HMAC_SECRET` torna a servire.

## 7. Fasi

### Fase 1 — Notifica (FATTA: `gateway/notify.py`, `tests/test_gateway_notify.py`)
1. Nessun `/whoami` necessario: l'ID di Luigi è già noto (letto dai log).
2. `gateway/notify.py` con canali Telegram ed email, liste da variabili d'ambiente. In questa fase il messaggio Telegram è
   solo testo con il Job ID: i bottoni diventano attivi in Fase 3, quando esistono storage e gestione dei `callback_query`.
3. Chiamata a `notify_review` quando lo stato diventa `needs_review` (percorso sync in `api.py`, percorso worker).
4. Contenuto della notifica: Job ID, canale, `chat_id` dell'utente, testo (troncato a 500 caratteri), riassunto del
   classificatore, prodotto e prezzo proposti, ora.
5. Anti-spam: massimo N notifiche al minuto, nessun duplicato per lo stesso Job ID.
6. Script di deploy: nuove variabili e secret; documentazione.

Test (scritti prima): lista email vuota o assente; un canale che fallisce non blocca l'altro; Telegram senza ID
configurati; escape del testo utente; deduplica; troncamento; nessun token o password nei log.

### Fase 2 — Storage persistente (FATTA nel codice: `gateway/jobstore.py`, `tests/test_gateway_jobstore.py`; da attivare con il redeploy)
1. `JobStore` con backend Firestore (collezione `jobs`), migrazione di `PipelineAdapter` e `QueueWorker`.
2. `GET /status/{job_id}` non risponde più 404 dopo un riavvio.
3. Il service account di Cloud Run riceve `roles/datastore.user`.

### Fase 3 — Approvazione (FATTA nel codice: `gateway/admin.py`, `gateway/admin_telegram.py`; da attivare con il redeploy)
1. Bottoni inline nel messaggio Telegram a Luigi: **Approva** (al prezzo proposto), **Rifiuta**, **Imposta prezzo** (risposta con un numero).
2. Gestione di `callback_query` in `/webhook/telegram` (oggi legge solo `message`).
3. Controllo `is_admin(chat_id)` su ogni azione; azioni idempotenti (un job già deciso non cambia).
4. Comandi di appoggio: `/pending` (elenco), `/approve <job_id> <prezzo>`, `/reject <job_id> <motivo>`.
5. Dopo la decisione: messaggio all'utente ("approvata, EUR X" / "non possiamo procedere") e riga di audit.
6. *Opzionale:* link email firmati come seconda via di approvazione: pagina di conferma `GET` (nessun effetto) e azione `POST`;
   firma con scadenza, una sola volta. Se non servono, l'email resta solo una notifica.

Test: utente non admin rifiutato; doppio clic; firma scaduta o manomessa; GET che non muta lo stato (SafeLinks);
l'utente riceve esattamente un messaggio di esito.

### Fase 4 — Richieste fraudolente (già in lista da fare)
Categoria `refused` nel classificatore: risposta di rifiuto all'utente, notifica a Luigi come "bloccata" (non da approvare).

### Fase 5 — Collegamento gateway → pipeline (decisioni del 2026-10-09)

**Decisioni di Luigi:** parte solo ciò che approva lui (nessun sistema di pagamento, quindi niente run automatiche per
sconosciuti); esecuzione con Cloud Tasks + un servizio worker privato; il risultato arriva prima a lui, con i bottoni
Invia al cliente / Scarta.

**Realizzato (PR 1/3):** `gateway/studio_runner.py` esegue la pipeline LangGraph senza Francesca (niente git push, email
Gmail, scritture nel repo); Marco usa il prezzo approvato; correzioni alla pipeline (prompt fattura/landing con graffe non
protette, approvazione di un rischio alto che ripartiva da Gianni).
**Realizzato (PR 2/3):** `gateway/pipeline_queue.py` (Cloud Tasks), `gateway/pipeline_worker.py` (servizio privato, `/run`),
`notify_result` (file + bottoni a Luigi), `/run` e Riprova, Dockerfile.worker, coda `max-attempts=1`, script di deploy.
**Realizzato (PR 3/3):** i bottoni Invia al cliente / Scarta con invio una tantum del file a chi l'ha chiesto (claim `delivering` prima di inviare, ripristino se Telegram rifiuta), `/file` e `/pending` esteso a risultati e run fallite.
**Non fatto, per scelta:** audit log in `process/audit/`, push su GitHub ed email di Francesca dal cloud; invio automatico a clienti non Telegram; pagamento (ISS-011).

Testo originale della proposta (per memoria):

Oggi il gateway classifica e notifica, ma **nessun job avvia la pipeline a 6 agenti**: anche un job `classified`
("il tuo deliverable è in lavorazione") resta fermo, e un job approvato da Luigi non produce nulla. Lo si è visto con la richiesta
`fd05c4448f` ("suggerimento per cena"), gestita a mano: Luigi ha deciso gratis (amico che prova il bot), la proposta
è stata scritta e inviata dal bot (`message_id 40`) senza passare da nessuna pipeline.

1. Dopo `classified` o `approved`, il job viene accodato per la pipeline (`scripts/run_pipeline_cli.py` o un `PipelineRunner`
   che usa `deliverables/2026-05-25_016_aistudio-langgraph`), con stato `in_progress` / `delivered` in Firestore.
2. Il risultato (testo o file) torna all'utente sullo stesso canale; errore e timeout portano il job in `failed` con avviso a Luigi.
3. Prezzo e prodotto arrivano dal job approvato (anche "gratis" con motivo), non dal listino.
4. Prima di partire: skill `/agentic-router` e `langgraph-*` (regola STEP 2 di `CLAUDE.md`), perché è codice LangGraph.
5. Cloud Run: la pipeline può superare il timeout della richiesta; serve un'esecuzione asincrona (Cloud Run Jobs o Cloud Tasks).

Dipende dalle Fasi 2 e 3 (job persistenti e stato di approvazione).

### Come funziona la Fase 3 (com'è stata realizzata)

- Il messaggio Telegram a Luigi porta quattro bottoni: **Approva EUR x** (solo se il prodotto ha un prezzo a catalogo), **Gratis**,
  **Imposta prezzo**, **Rifiuta**. "Imposta prezzo" chiede il prezzo con una risposta forzata (nessuno stato da salvare: il
  Job ID è nel testo del messaggio a cui rispondi).
- Comandi: `/pending` (schede con bottoni), `/approve <id> [prezzo|gratis]`, `/prezzo <id> <prezzo>`, `/reject <id> [motivo]`.
- La decisione è atomica (`JobStore.transition`, transazione in Firestore): due clic o due comandi producono una sola decisione.
  Il secondo vede "Già deciso".
- Dopo la decisione la scheda perde i bottoni e mostra l'esito; la persona che ha fatto la richiesta riceve un messaggio
  (approvata con il prezzo, gratuita, oppure "non possiamo procedere"). Il motivo di un rifiuto resta interno.
- Solo l'ID numerico di Luigi (`ADMIN_TELEGRAM_IDS`, altrimenti `NOTIFY_TELEGRAM_CHAT_IDS`) decide. Un comando scritto da altri
  riceve "Comando non disponibile" e non diventa mai una richiesta.
- **Verifica dell'origine.** L'ID di Luigi sta nel payload, che chiunque può falsificare. Il webhook accetta quindi aggiornamenti
  solo con l'intestazione `X-Telegram-Bot-Api-Secret-Token` uguale a `TELEGRAM_WEBHOOK_SECRET` (registrato con `setWebhook`).
  Senza quel segreto le funzioni di Luigi restano spente; gli utenti normali vengono serviti.
- Non fatto: i link firmati nelle email come seconda via di approvazione (opzionale, vedi sopra).

## 8. Sicurezza e privacy

- Nessuna password o token nei log: `httpx` è già silenziato; l'errore SMTP non deve riportare le credenziali.
- Solo l'ID numerico di Luigi (`NOTIFY_TELEGRAM_CHAT_IDS`) può approvare; lo username da solo non basta, può cambiare.
  Ogni `callback_query` viene controllato contro quell'ID prima di toccare il job.
- Le email contengono il testo degli utenti: dati personali (GDPR). Informativa nel `/start` e retention definita.
- Il testo utente nel messaggio a Luigi è dato non fidato: nessun `parse_mode` o escape, nessuna esecuzione di istruzioni.
- Limite di frequenza sulle notifiche, per non diventare un canale di spam verso Luigi.

## 9. Ordine consigliato e stima

| Fase | Cosa | Stima | Dipende da |
|------|------|-------|-----------|
| 0 | Scegliere lo storage; creare la password per app Gmail (Account Google → Sicurezza → Password per le app) | 15 minuti (tuo) | — |
| 1 | Notifica Telegram + email | mezza giornata | Fase 0 |
| 2 | Firestore | mezza giornata | — |
| 3 | Approvazione | 1 giornata | Fasi 1 e 2 |
| 4 | Blocco fraudolente | 2-3 ore | — |
| 5 | Collegamento gateway → pipeline | 1-2 giorni | Fasi 2 e 3 |

## 10. Chiusura (CLAUDE.md)

Prodotto interno, prezzo 0.00. A fine lavoro: audit log in `process/audit/`, cartella deliverable, riga in "Delivered Requests",
branch `claude/<slug>`, PR e merge. Redeploy a carico di Luigi (vedi `docs/cloud-run-setup.md`).
