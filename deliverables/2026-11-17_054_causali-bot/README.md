# 054 — Bot Telegram per le causali (estensione di 045)

Mandi dal telefono `250 credem pulizie Valeria`, confermi con **Salva**, e `bankanalyst` trova la
causale da solo la prossima volta che analizzi gli estratti. Niente YAML a mano, niente computer acceso.

Stato: **codice mergiato, non ancora deployato.** 58 test offline nuovi. Non provato con Telegram, Firestore
né Cloud Run veri; l'immagine Docker non è stata costruita (nessun Docker sul laptop).

## Decisioni di Luigi (2026-11-17)

| Domanda | Decisione |
|---|---|
| Banca di default | **Nessuna.** Va sempre scritta (`credem` / `ing` / `fineco`); senza, il bot spiega cosa manca e non salva nulla |
| Dove stanno i dati | **Database Firestore separato** `causali`, non il `(default)` dei job |
| Conservazione | **24 mesi** dalla data del movimento (TTL su `expire_at`) |
| Foto della ricevuta | **Non ora.** Ogni causale ha già il campo `allegati` (vuoto): in futuro si potrà allegare e conservare una foto senza migrare nulla |

## Come si scrive

| Scrivi | Diventa |
|---|---|
| `250 credem pulizie Valeria` | oggi, credem, -250,00, "Pulizie Valeria" |
| `ieri 40 ing parrucchiere` | ieri, ing, -40,00 |
| `15/11 +120 credem rimborso Marco` | 15/11, credem, **+120,00** (entrata) |
| `pulizie 250` | **errore: manca la banca** |

Importo: il primo numero (`250`, `250,50`, `1.250,50`). Uscita di default; `+`, `entrata`, `ricevuto`,
`accredito` la rendono entrata. Data: `oggi` (ora di Roma), `ieri`, `gg/mm` (mai nel futuro) o
`gg/mm/aaaa`. Il resto è la causale. Letto **a regole**: nessun modello, niente va a OpenAI.

Il bot risponde con una scheda e salva solo dopo **Salva**:

```
17/11/2026 · Credem · -250,00 €
Pulizie Valeria
Categoria: Casa e utenze
[ Salva ]  [ Categoria ▸ ]  [ Annulla ]
```

La categoria è indovinata dalle regole di base (`bankanalyst/rules.yaml`); **Categoria ▸** la cambia.
Le regole personali restano sul laptop. Comandi: `/ultime` (ultime 10), `/annulla` (toglie l'ultima,
entro 10 minuti), `/help`. Una foto riceve la risposta "per ora solo testo".

## Come arrivano a bankanalyst

Automatico. `python -m bankanalyst estratti_conto/ …` legge **tutte** le causali dal cloud e le unisce
a quelle del file personale (doppioni tolti). Si abilita con `CAUSALI_FIRESTORE_PROJECT=aistudio-milano`
in `.env`; senza, funziona come prima. `--no-causali-cloud` fa un giro senza.

Se il cloud non risponde (offline, credenziali scadute) `bankanalyst` **non si ferma**: stampa
`ATTENZIONE: causali cloud non raggiungibili (…)`, aggiunge una riga al foglio **Controlli** e va
avanti con le causali locali.

## Messa in funzione (Luigi)

1. @BotFather → `/newbot` → token in `.env` come `TELEGRAM_CAUSALI_BOT_TOKEN`; `/setjoingroups` → Disable.
2. Il tuo ID numerico in `.env` come `CAUSALI_ALLOWED_CHAT_ID` (lo stesso del bot admin).
3. `./scripts/deploy_causali_bot.sh --dry-run`, leggi i comandi, poi senza `--dry-run`.
4. Apri il bot, **Start**, manda `250 credem pulizie Valeria`, premi Salva.
5. Sul laptop, una volta: `gcloud auth application-default login`, poi `CAUSALI_FIRESTORE_PROJECT` in `.env`.
6. Controllo: `python scripts/check_telegram.py --only causali`.

## Cosa crea il deploy

- Database Firestore `causali` (Milano), TTL su `expire_at` per `causali` (24 mesi) e `bozze` (1 giorno),
  protezione dalla cancellazione.
- Service account `causali-bot`, con `roles/datastore.user` **solo su quel database** (condizione IAM):
  il gateway e il worker non lo vedono, e il bot non vede i job.
- Il tuo account: `roles/datastore.viewer` sullo stesso database (sola lettura, per `bankanalyst`).
- Secret `TELEGRAM_CAUSALI_BOT_TOKEN` e `TELEGRAM_CAUSALI_WEBHOOK_SECRET`.
- Servizio Cloud Run `causali-bot`: una sola istanza, scala a zero; pubblico solo perché Telegram lo
  raggiunga. Ogni chiamata richiede l'header `X-Telegram-Bot-Api-Secret-Token` (403 altrimenti) e
  risponde solo al tuo ID numerico; gli altri non ricevono risposta e il testo non è mai nei log.

## Da verificare al primo deploy

- La **condizione IAM** sul database (`resource.name == "projects/…/databases/causali"`): scritta dalla
  documentazione, mai eseguita. Se Firestore risponde "permission denied", è il primo posto dove guardare.
- La creazione del TTL su un database con nome (`gcloud firestore fields ttls update … --database=causali`).
- Costo atteso: zero nel free tier (qualche messaggio al giorno).

## Foto delle ricevute (più avanti)

Il documento ha già `allegati: []`. Per aggiungerle servirà un bucket privato per le immagini (con
scadenza alla pari delle causali) e un gestore per `message.photo`; il formato previsto per ogni
elemento è `{"tipo": "foto", "ref": "gs://…"}`. Nessun dato esistente va migrato.

## File

`causalibot/` (`parser.py`, `store.py`, `categories.py`, `app.py`, `Dockerfile`) ·
`bankanalyst/causali_cloud.py` · `scripts/deploy_causali_bot.sh` · `deploy/cloudbuild.causali.yaml` ·
`scripts/cloudrun_lib.sh` (database con nome) · `scripts/check_telegram.py` (`--only`) ·
piano: `docs/plans/bankanalyst-telegram-causali.md`.
