# Piano — notifica e approvazione di Luigi per le richieste `needs_review`

Stato: **proposta, nulla implementato**. Data: 2026-10-09.
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
| Un bot Telegram **non può scrivere a un `@username` privato**: `sendMessage` vuole l'ID numerico, e solo dopo che l'utente ha premuto Start sul bot | `@acetoluigi` deve scrivere `/start` a `@AIStudioMilanoBot`; serve ricavare il suo `chat_id` numerico (comando `/whoami`) |
| Cloud Run ha filesystem effimero | L'approvazione richiede uno storage persistente (Firestore consigliato) |
| Cloud Run blocca la porta 25 in uscita; 465/587 sono ok | Email via SMTP submission (587) o API HTTP |
| Hotmail/Outlook tende a mettere in spam i mittenti nuovi | Mittente con SPF/DKIM validi (Gmail o dominio verificato); testare la cartella spam |
| I client email (Outlook SafeLinks) aprono in automatico i link `GET` | Un link email non deve approvare con un semplice GET: serve una pagina di conferma con POST |
| Il testo dell'utente finisce in un messaggio a Luigi | Va escluso il Markdown/HTML iniettato: niente `parse_mode` sul testo utente, oppure escape |

## 4. Decisioni aperte (servono prima di iniziare)

1. **Trasporto email.** Opzioni:
   - **A. SMTP di Gmail** con password per app di `luigi.vinegar@gmail.com`, in Secret Manager. Zero costi, 500 mail/giorno,
     pronto in 10 minuti. *Consigliata per partire.*
   - **B. Servizio transazionale (Resend / SendGrid)** con dominio verificato: migliore consegna su Hotmail, serve un dominio.
   - **C. Gmail API OAuth**: sconsigliata, i token di sessione non sono adatti a un servizio headless.
2. **ID numerico di `@acetoluigi`.** Nei log compare `chat=190776580` (la sessione del test del 2026-10-09 alle 10:25):
   se è il tuo, basta confermarlo; altrimenti si usa `/whoami`.
3. **Storage.** Firestore (consigliato: gratis a questi volumi, nativo su GCP) o Cloud SQL.
4. **Chi può approvare.** Solo gli ID Telegram in `NOTIFY_TELEGRAM_CHAT_IDS`, o anche altri?

## 5. Configurazione

Gli indirizzi non vanno nel codice. Variabili d'ambiente del servizio `gateway`, lette da `.env` dallo script di deploy:

```
NOTIFY_EMAILS=stekkino@hotmail.it            # lista separata da virgole
NOTIFY_TELEGRAM_CHAT_IDS=190776580           # ID numerici; @acetoluigi mappato qui
NOTIFY_TELEGRAM_USERNAMES=acetoluigi         # solo per /whoami e controllo autorizzazioni
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
- `gateway/jobstore.py` — interfaccia `JobStore` (get, put, update_status, list_by_status) con implementazione file
  (test e locale) e Firestore (produzione).
- `gateway/admin.py` — autorizzazione (`is_admin(chat_id)`), firma dei link email (HMAC-SHA256, scadenza),
  rotte `/admin/job/...`. Qui `GATEWAY_HMAC_SECRET` torna a servire.

## 7. Fasi

### Fase 1 — Notifica (piccola, subito utile)
1. Comando `/whoami` nel webhook: risponde con `chat_id` e `username` (solo l'ID, nessun dato sensibile).
2. `gateway/notify.py` con canali Telegram ed email, liste da variabili d'ambiente.
3. Chiamata a `notify_review` quando lo stato diventa `needs_review` (percorso sync in `api.py`, percorso worker).
4. Contenuto della notifica: Job ID, canale, `chat_id` dell'utente, testo (troncato a 500 caratteri), riassunto del
   classificatore, prodotto e prezzo proposti, ora.
5. Anti-spam: massimo N notifiche al minuto, nessun duplicato per lo stesso Job ID.
6. Script di deploy: nuove variabili e secret; documentazione.

Test (scritti prima): lista email vuota o assente; un canale che fallisce non blocca l'altro; Telegram senza ID
configurati; escape del testo utente; deduplica; troncamento; nessun token o password nei log.

### Fase 2 — Storage persistente
1. `JobStore` con backend Firestore (collezione `jobs`), migrazione di `PipelineAdapter` e `QueueWorker`.
2. `GET /status/{job_id}` non risponde più 404 dopo un riavvio.
3. Il service account di Cloud Run riceve `roles/datastore.user`.

### Fase 3 — Approvazione
1. Bottoni inline nel messaggio Telegram: **Approva**, **Rifiuta**, **Imposta prezzo** (risposta con un numero).
2. Gestione di `callback_query` in `/webhook/telegram` (oggi legge solo `message`).
3. Controllo `is_admin(chat_id)` su ogni azione; azioni idempotenti (un job già deciso non cambia).
4. Comandi di appoggio: `/pending` (elenco), `/approve <job_id> <prezzo>`, `/reject <job_id> <motivo>`.
5. Dopo la decisione: messaggio all'utente ("approvata, EUR X" / "non possiamo procedere") e riga di audit.
6. Link email firmati: pagina di conferma `GET` (nessun effetto) e azione `POST`; firma con scadenza, una sola volta.

Test: utente non admin rifiutato; doppio clic; firma scaduta o manomessa; GET che non muta lo stato (SafeLinks);
l'utente riceve esattamente un messaggio di esito.

### Fase 4 — Richieste fraudolente (già in lista da fare)
Categoria `refused` nel classificatore: risposta di rifiuto all'utente, notifica a Luigi come "bloccata" (non da approvare).

## 8. Sicurezza e privacy

- Nessuna password o token nei log: `httpx` è già silenziato; l'errore SMTP non deve riportare le credenziali.
- Solo gli ID in `NOTIFY_TELEGRAM_CHAT_IDS` possono approvare; l'username da solo non basta, può cambiare.
- Le email contengono il testo degli utenti: dati personali (GDPR). Informativa nel `/start` e retention definita.
- Il testo utente nel messaggio a Luigi è dato non fidato: nessun `parse_mode` o escape, nessuna esecuzione di istruzioni.
- Limite di frequenza sulle notifiche, per non diventare un canale di spam verso Luigi.

## 9. Ordine consigliato e stima

| Fase | Cosa | Stima | Dipende da |
|------|------|-------|-----------|
| 0 | Decisioni della sezione 4, password per app Gmail, Start di `@acetoluigi` | 15 minuti (tuo) | — |
| 1 | Notifica Telegram + email | mezza giornata | Fase 0 |
| 2 | Firestore | mezza giornata | — |
| 3 | Approvazione | 1 giornata | Fasi 1 e 2 |
| 4 | Blocco fraudolente | 2-3 ore | — |

## 10. Chiusura (CLAUDE.md)

Prodotto interno, prezzo 0.00. A fine lavoro: audit log in `process/audit/`, cartella deliverable, riga in "Delivered Requests",
branch `claude/<slug>`, PR e merge. Redeploy a carico di Luigi (vedi `docs/cloud-run-setup.md`).
