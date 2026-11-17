# Piano — bot Telegram per le causali degli estratti conto (estensione 045)

Stato: **decisioni prese il 2026-11-17, costruito** (consegna 054, guida in `deliverables/2026-11-17_054_causali-bot/`). Non ancora deployato.
Revisione 2: il bot **non gira sul laptop**. Gira su Cloud Run, sempre raggiungibile.
Revisione 3: il bot **raccoglie e basta**. Le causali le prende `bankanalyst` da solo, ogni volta che
gira su tutti gli estratti: niente esportazioni a mano, niente passaggi in mezzo.

## Cosa serve

Mandare dal telefono una riga tipo `250 credem pulizie Valeria` e ritrovarla nelle causali che
`bankanalyst` usa (vedi "Segnare la causale di un movimento" nella guida 045), in qualunque momento,
senza scrivere YAML a mano e senza un computer acceso.

## Perché un bot e non un "canale"

Un canale Telegram è a senso unico: chi lo gestisce pubblica, gli altri leggono. Per *mandare*
informazioni serve un **bot in chat privata**. Quindi: un bot nuovo, solo per questo.

## Separato da tutto il resto

| Bot esistente | Token | Dove gira |
|---|---|---|
| Bot clienti / pipeline | `TELEGRAM_BOT_TOKEN` | servizio `gateway` |
| Bot RAG | `TELEGRAM_RAG_BOT_TOKEN` | servizio `rag-api` |
| Bot admin (041) | `TELEGRAM_ADMIN_BOT_TOKEN` | servizio `gateway` |
| **Bot causali (nuovo)** | **`TELEGRAM_CAUSALI_BOT_TOKEN`** | **servizio nuovo `causali-bot`** |

Separato a ogni livello, non solo nel token:

- **Servizio Cloud Run a parte** (`causali-bot`), stesso progetto `aistudio-milano`, regione
  `europe-west8`. Non è una rotta del gateway: un problema nel gateway clienti non tocca le causali e
  viceversa.
- **Database Firestore a parte**, con nome (`causali`), non il `(default)` dei job. Un database con
  nome ha i suoi permessi: il service account del gateway e del worker non lo vedono.
- **Service account a parte** (`causali-bot@…`), con un solo ruolo: `roles/datastore.user` con
  condizione IAM sul database `causali`. Nessun altro accesso nel progetto.
- **Secret a parte** in Secret Manager: token del bot e `secret_token` del webhook.

## Dove gira: Cloud Run, webhook

- Telegram chiama `POST /webhook/telegram-causali` sul servizio; il servizio controlla l'header
  `X-Telegram-Bot-Api-Secret-Token` (come fa già il gateway, `gateway/api.py`) e risponde 403 a
  tutto il resto.
- Scale to zero: costa zero quando non lo usi; la prima risposta dopo un periodo di inattività
  arriva in 1-2 secondi. Qualche messaggio al giorno sta ampiamente nel free tier di Cloud Run e
  di Firestore.
- Nessun messaggio perso: il webhook è sempre raggiungibile; se il servizio risponde con un errore,
  Telegram riprova da solo.
- `/health` per il controllo, log JSON senza il testo dei messaggi.

## Come si usa

Messaggio libero, letto **a regole** (niente modello, niente dati inviati a OpenAI):

| Scrivi | Diventa |
|---|---|
| `250 credem pulizie Valeria` | oggi, credem, -250.00, "pulizie Valeria" |
| `ieri 40 ing parrucchiere` | ieri, ing, -40.00 |
| `15/11 +120 credem rimborso Marco` | 15/11, credem, **+120.00** (entrata) |
| `pulizie 250` | **errore: manca la banca** (nessun default) |

- Importo: il primo numero (`250`, `250,50`, `1.250`). Uscita di default; `+`, "entrata", "ricevuto"
  la rendono entrata.
- Banca: `credem` / `ing` / `fineco`, **obbligatoria**.
- Data: `oggi` (default, ora di Roma), `ieri`, `gg/mm` o `gg/mm/aaaa`.
- Tutto il resto è la causale.
- Categoria: le regole di base di `bankanalyst` (`bankanalyst/rules.yaml`, nell'immagine) girano sul
  testo della causale; se non trovano nulla, il bot propone le categorie più usate come bottoni. Le
  regole personali restano sul laptop e non vanno nel cloud.

Il bot risponde con una **scheda di conferma**, e salva solo dopo **Salva**:

```
17/11/2026 · Credem · -250,00 €
Pulizie Valeria
Categoria: Casa e utenze
[ Salva ]  [ Categoria ▸ ]  [ Annulla ]
```

Comandi: `/ultime` (ultime 10), `/annulla` (toglie l'ultima, entro 10 minuti), `/help`.

## Dove stanno i dati e come arrivano a bankanalyst

- Ogni causale è un documento nel database `causali`: `data`, `banca`, `importo` (stringa, per non
  perdere i centesimi), `causale`, `categoria`, `creata_il`, `expire_at`.
- **Conservazione:** `expire_at` = data del movimento + 24 mesi, con TTL di Firestore (come i job,
  037). Dopo, la causale si cancella da sola; nel file YAML sul laptop resta.
- Protezione dalla cancellazione accidentale del database (come per `(default)`).
- **Verso bankanalyst: automatico.** Quando gira `python -m bankanalyst estratti_conto/ …`, come
  primo passo legge **tutte** le causali dal database `causali` e le unisce a quelle del file
  personale (se ce ne sono). Nessun file da scaricare, nessun comando in più. Il bot non deve
  sapere nulla degli estratti: raccoglie, e basta.
  - Credenziali sul laptop: una volta `gcloud auth application-default login`; l'account di Luigi
    ha un ruolo di **sola lettura** sul database `causali`.
  - Attivo se c'è `CAUSALI_FIRESTORE_PROJECT=aistudio-milano` in `.env`; senza, `bankanalyst`
    lavora come oggi.
  - Se il cloud non risponde (offline, credenziali scadute) `bankanalyst` non si ferma: avvisa a
    schermo e nel foglio Controlli, e va avanti con le causali locali.
  - `--no-causali-cloud` per un giro senza.
- Le causali si abbinano a qualunque estratto passi, vecchio o nuovo: il bot non ha bisogno degli
  estratti e il cloud non ne vede nessuno.
- Le causali "in attesa" (senza movimento) restano dove sono già: foglio **Causali in attesa**
  dell'Excel. Il cloud non vede gli estratti, quindi non può saperlo.

## Sicurezza

- Risponde solo all'ID numerico di Luigi (`CAUSALI_ALLOWED_CHAT_ID`); gli altri vengono ignorati
  senza risposta e senza log del testo. Lo stesso controllo sui bottoni (callback).
- In @BotFather: `/setjoingroups` → Disable, nessuna descrizione che riveli lo scopo.
- Webhook con `secret_token`; servizio pubblico solo su quella rotta e su `/health`.
- Token e `secret_token` in Secret Manager, mai in variabili in chiaro né nei log.
- I dati personali stanno solo nel database `causali` (cifrato a riposo da Google) e in Telegram.
  Niente PDF, saldi o descrizioni bancarie nel cloud: solo quello che scrivi tu nel messaggio.
- `scripts/check_telegram.py` controlla anche il nuovo token (getMe, webhook atteso sul servizio
  `causali-bot`, non uguale agli altri tre).

## Lavoro stimato

- `causalibot/`: `parser.py` (messaggio → causale), `store.py` (Firestore, database `causali`),
  `app.py` (FastAPI: webhook, scheda, bottoni, comandi), `Dockerfile` (include
  `bankanalyst/rules.yaml` per indovinare la categoria).
- `bankanalyst/causali_cloud.py`: lettura del database `causali` all'avvio, unione con le causali
  del file personale, avviso (non errore) se il cloud non risponde; `--no-causali-cloud`.
- `scripts/deploy_causali_bot.sh` sul modello di `deploy_cloudrun.sh`: database con nome + TTL +
  protezione, service account con condizione IAM, secret, build, deploy, `setWebhook` con
  `secret_token`, verifica; `--dry-run` per vedere i comandi prima.
- Test offline: parser (date, segno, banca, importi italiani), ID non autorizzato ignorato, header
  del webhook sbagliato → 403, salvataggio solo dopo Salva, `/annulla` entro 10 minuti, causali lette
  da `bankanalyst` con Firestore finto, cloud irraggiungibile → avviso e si va avanti.
  Nessuna rete nei test.

Prezzo: interno (estensione di 045), 0.00. Costo di esercizio atteso: zero nel free tier.

## Decisioni di Luigi (2026-11-17)

Le proposte qui sotto sono state decise così:

1. Banca di default: **nessuna**, va sempre scritta (niente `CAUSALI_DEFAULT_BANK`; senza banca il bot non salva).
2. Database Firestore **separato** (`causali`).
3. Conservazione: **24 mesi**.
4. Foto della ricevuta: **non ora**, ma il documento ha già `allegati: []` per aggiungerle e conservarle in futuro.

Testo originale delle domande:

1. Banca di default: credem?
2. Database Firestore separato (proposto) o una collection nel `(default)` dei job? Separato costa
   uguale e tiene i dati bancari lontani dai service account del gateway.
3. Conservazione nel cloud: 24 mesi (proposto), meno, o per sempre?
4. Foto della ricevuta: per ora no (vorrebbe dire un bucket con immagini personali); da aggiungere
   dopo se serve.

## Prima di accenderlo (Luigi)

1. @BotFather → `/newbot` → token in `.env` come `TELEGRAM_CAUSALI_BOT_TOKEN`; `/setjoingroups` →
   Disable.
2. Il tuo ID numerico in `CAUSALI_ALLOWED_CHAT_ID` (lo stesso del bot admin).
3. `scripts/deploy_causali_bot.sh --dry-run`, poi senza `--dry-run`.
4. Apri il bot, premi Start, manda `250 credem pulizie Valeria` come prima prova.
