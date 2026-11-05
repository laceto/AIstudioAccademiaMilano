# 048 — Dallo smoke test al deliverable

Lo smoke test del gateway (046) si fermava a `needs_review`: in produzione lì il job aspetta il
bottone di Luigi. Con `run_pipeline` l'Action va avanti e produce il deliverable vero.

## Come si lancia

Actions → **Gateway smoke test** → Run workflow:

| Campo | Valore |
|-------|--------|
| `target` | `local` |
| `request` | es. `Fai uno script Python che crea una lista` |
| `run_pipeline` | ✔ |
| `pipeline_provider` | `openai` (secret `OPENAI_API_KEY`) o `anthropic` (secret `ANTHROPIC_API_KEY`) |

Cosa succede nel runner, tutto sul job store a file del runner (mai Firestore, mai Telegram):

1. gateway avviato, richiesta su `/submit` con la chiave usa e getta, worker → `needs_review`;
2. `scripts/gateway_deliver.py` approva il job a prezzo 0 con `gateway.admin.decide`, come il bottone *Gratis*;
3. chiama il worker vero della pipeline (`gateway/pipeline_worker.py`, `POST /run`): `approved → running → awaiting_review` (o `failed`);
4. scrive il risultato e lo carica come artifact.

## Dove si controlla l'output

Nella pagina del run (Actions → il run):

- **Summary**: tabella dei controlli del gateway, poi la scheda *Deliverable* con stato, prodotto, QA, rischio e il contenuto del file (fino a 20.000 caratteri).
- **Artifacts → `deliverable`** (zip, tenuto 14 giorni):
  - il file prodotto da Chiara (es. `crea_lista.py`), solo se il run è riuscito;
  - `result.json`: stato, prezzo, prodotto, QA, rischio, errore;
  - `steps.txt`: la traccia degli agenti (Stacy, Gianni, Chiara, revisori, Marco, Francesca).

Se lo stato è `failed`, l'errore è nella Summary e in `result.json`; il passo è rosso.

## Cosa NON fa

- Non tocca il gateway su Cloud Run: lì i job di `/submit` restano `queued` e il deliverable arriva
  solo dal flusso Telegram (Luigi approva → worker → file a Luigi su Telegram → *Invia al cliente*).
- Non committa niente nel repository: per un deliverable da consegnare con branch e audit c'è
  l'altro workflow, **AI Studio Pipeline** (`pipeline.yml`).

## Costi

Ogni run con `run_pipeline` chiama il modello più volte (tutti gli agenti). Il job parte solo a mano.

## Prova

6 test offline (`tests/test_gateway_deliver.py`, pipeline finta). Giro reale nel container senza
chiave LLM: la catena gateway → approvazione → worker → pipeline arriva fino agli agenti, che si
fermano per la chiave mancante (`failed`, errore chiaro in `result.json`). Con una chiave vera non è
ancora stato provato.
