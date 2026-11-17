# Piano — bot Telegram per le causali degli estratti conto (estensione 045)

Stato: **proposta, niente codice**. Da decidere con Luigi prima di costruire.

## Cosa serve

Mandare dal telefono una riga tipo `250 credem pulizie Valeria` e ritrovarla nel file delle causali
che `bankanalyst` legge (vedi "Segnare la causale di un movimento" nella guida 045), senza aprire il
laptop e senza scrivere YAML a mano.

## Perché un bot e non un "canale"

Un canale Telegram è a senso unico: chi lo gestisce pubblica, gli altri leggono. Per *mandare*
informazioni serve un **bot in chat privata**. Quindi: un bot nuovo, solo per questo.

## Separato da tutto il resto

| Bot esistente | Token | Uso |
|---|---|---|
| Bot clienti / pipeline | `TELEGRAM_BOT_TOKEN` | richieste dei clienti, calendar sentinel |
| Bot RAG | `TELEGRAM_RAG_BOT_TOKEN` | domande sul repo |
| Bot admin (041) | `TELEGRAM_ADMIN_BOT_TOKEN` | approvazioni di Luigi |
| **Bot causali (nuovo)** | **`TELEGRAM_CAUSALI_BOT_TOKEN`** | **solo movimenti personali** |

Motivi per non riusare il bot admin: i dati bancari personali non passano dal gateway, da Firestore né
da Cloud Run; un errore nel bot dei clienti o in quello admin non può esporre le causali; il bot si
può spegnere o revocare da solo.

## Dove gira: sul laptop, in polling

- Il file delle causali sta dove stanno i PDF (`estratti_conto/`, fuori da git). Il bot gira **sul
  laptop** con long polling: niente URL pubblico, niente cloud, niente dati personali fuori casa.
- Telegram tiene i messaggi non letti per 24 ore: se mandi una causale a laptop spento, viene
  salvata alla prossima accensione (entro 24 ore). Avvio automatico al login con Task Scheduler.
- Alternativa scartata: webhook su Cloud Run + Firestore + sincronizzazione sul laptop. Più pezzi,
  e i movimenti personali finirebbero nel cloud. Da riconsiderare solo se il limite delle 24 ore
  diventa un problema.

## Come si usa

Messaggio libero, letto **a regole** (niente modello, niente dati inviati a OpenAI):

| Scrivi | Diventa |
|---|---|
| `250 credem pulizie Valeria` | oggi, credem, -250.00, "pulizie Valeria" |
| `ieri 40 ing parrucchiere` | ieri, ing, -40.00 |
| `15/11 +120 credem rimborso Marco` | 15/11, credem, **+120.00** (entrata) |
| `pulizie 250` | banca di default (`CAUSALI_DEFAULT_BANK`, es. credem) |

- Importo: il primo numero (`250`, `250,50`, `1.250`). Uscita di default; `+`, "entrata", "ricevuto"
  la rendono entrata.
- Banca: `credem` / `ing` / `fineco`, se manca quella di default.
- Data: `oggi` (default), `ieri`, `gg/mm` o `gg/mm/aaaa`.
- Tutto il resto è la causale.
- Categoria: le regole di `bankanalyst` girano sul testo della causale; se non trovano nulla, il bot
  propone le categorie più usate come bottoni.

Il bot risponde con una **scheda di conferma**, e scrive solo dopo **Salva**:

```
17/11/2026 · Credem · -250,00 €
Pulizie Valeria
Categoria: Casa e utenze
[ Salva ]  [ Categoria ▸ ]  [ Annulla ]
```

Comandi: `/ultime` (ultime 10 causali), `/annulla` (toglie l'ultima, entro 10 minuti),
`/attesa` (causali non ancora abbinate a un movimento, prese dall'ultimo giro di `bankanalyst`),
`/help`.

## Scrittura del file

- File a parte, `estratti_conto/causali.yaml`, scritto solo dal bot. Non tocca `mie_regole.yaml`
  (lì ci sono i commenti di Luigi: riscriverlo li perderebbe).
- `bankanalyst` legge le `causali` da entrambi: `load_rules` carica anche `causali.yaml` se esiste
  nella stessa cartella del file di regole (o `--causali <file>`).
- Scrittura atomica (file temporaneo + rename) e copia `.bak` prima di ogni modifica. Un `id` per
  riga, così `/annulla` toglie quella giusta.
- `bankanalyst` scrive `estratti_conto/.causali_in_attesa.json` a ogni giro: lo legge `/attesa`.

## Sicurezza

- Risponde solo all'ID numerico di Luigi (`CAUSALI_ALLOWED_CHAT_ID`); gli altri vengono ignorati
  senza risposta e senza log del testo.
- In @BotFather: `/setjoingroups` → Disable (niente gruppi), nessuna descrizione che riveli lo scopo.
- Token solo in `.env`; mai loggato. Il testo dei messaggi non va nei log (solo "salvata causale id N").
- `scripts/check_telegram.py` controlla anche il nuovo token (getMe, nessun webhook attivo,
  non uguale agli altri tre).
- Il pre-commit già blocca `.env`; `estratti_conto/**` è già in `.gitignore`.

## Lavoro stimato

Modulo `bankanalyst/telegram_causali.py` (parser, scheda, scrittura, comandi) + avvio
`python -m bankanalyst.telegram_causali`. Test offline: parser (date, segno, banca, importi italiani),
ID non autorizzato ignorato, scrittura atomica e `/annulla`, `load_rules` che unisce `causali.yaml`.
Nessuna rete nei test: le chiamate a Telegram sono finte.

Prezzo: interno (estensione di 045), 0.00.

## Da decidere con Luigi

1. Banca di default: credem?
2. Va bene "solo laptop" con il limite delle 24 ore, o serve sempre acceso (cloud)?
3. Un file `causali.yaml` separato (proposto) o dentro `mie_regole.yaml`?
4. Foto dello scontrino o della ricevuta allegata alla causale: utile o superflua?

## Prima di accenderlo (Luigi)

1. @BotFather → `/newbot` → nome a scelta → token in `.env` come `TELEGRAM_CAUSALI_BOT_TOKEN`.
2. Il tuo ID numerico in `CAUSALI_ALLOWED_CHAT_ID` (lo stesso già usato per il bot admin).
3. Apri il bot e premi Start.
