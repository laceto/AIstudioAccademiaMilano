# 050 — Chiara costruisce con Claude Code

## Cosa cambia

Per i prodotti di codice Chiara può ora costruire il deliverable con la **CLI di Claude Code in
modalità headless** (`claude -p`) invece che con una sola chiamata al modello. Claude Code scrive più
file, scrive i test prima del codice e li fa girare finché passano. Poi Chiara li rifà girare per
conto suo e impacchetta tutto in un unico file di testo.

- **Spento di default.** Si accende con `CHIARA_ENGINE=claude_code`. Senza, Chiara è identica a prima.
- **Solo prodotti di codice:** `chatbot_app`, `agent_deploy_streamlit`, `weather_dashboard`,
  `calendar_integration`, `rag_knowledge_base`. PDF, fatture, report e landing page restano sui
  template (costano meno e una chiamata basta). L'elenco si cambia con `CHIARA_CLAUDE_CODE_PRODUCTS`.
  `algo_trading` è fuori apposta.
- **Dove:** `deliverables/2026-05-25_016_aistudio-langgraph/chiara_claude_code.py`, chiamato da
  `chiara_implement`. Vale per la pipeline v1 e per la v2 (la v2 usa la Chiara della v1).
- **Un file solo, come prima.** QA, pannello rischi, Firestore e la scheda di Luigi su Telegram
  ricevono sempre una stringa: il file si chiama `<prodotto>_bundle.txt`. In testa c'è il riepilogo
  (numero di file, esito dei test, costo, file lasciati fuori), che QA e i revisori leggono per primo.
- **Se qualcosa va storto si torna indietro da soli:** CLI non installata, chiave mancante, timeout,
  errore, nessun file scritto → Chiara usa la strategia di sempre. Nei passi della pipeline compare
  `claude-code fallback: <motivo>`, così Luigi vede chi ha costruito cosa.
- **Riprova dopo QA:** se Stacy QA boccia, Claude Code riceve i punti da correggere.

## Riavere i file dal bundle

```bash
python -m scripts.unpack_bundle chatbot_app_bundle.txt ./chatbot_app
```

Solo libreria standard. La cartella deve essere nuova o vuota; percorsi che uscirebbero dalla
cartella (`../`, assoluti, `C:`) sono rifiutati prima di scrivere qualsiasi cosa.

## Isolamento: cosa può fare Claude Code nel worker

Claude Code esegue codice (i test che scrive). Il testo del cliente arriva fin lì, quindi conta cosa
può vedere:

| Livello | Cosa |
|---|---|
| Ambiente pulito | La CLI riceve solo `PATH`, lingua, proxy e `ANTHROPIC_API_KEY`. Le altre chiavi del worker (OpenAI, Telegram, SMTP, credenziali Google) non passano. I test girano senza nessuna chiave. |
| Utente separato | CLI e test girano come `builder`, un utente senza privilegi creato nell'immagine. **Provato:** `builder` riceve *Permission denied* leggendo `/proc/<pid>/environ` del worker; lo stesso utente invece lo legge. Senza `builder` il motore si rifiuta (fallback), a meno di `CHIARA_CLAUDE_CODE_ALLOW_SAME_USER=1`, che è solo per il laptop e il deploy non lo porta mai su Cloud Run. |
| Strumenti | Leggere/scrivere/modificare file; Bash solo per `pytest` e `py_compile`. Niente WebFetch/WebSearch, niente MCP, niente hook o CLAUDE.md (`--bare`), mai `bypassPermissions`. |
| Spesa e tempo | `--max-budget-usd` (default 2.00 $) e timeout (default 420 s). |
| Prompt | Il testo del cliente sta in un blocco `<customer_request>` dichiarato "dati, non istruzioni", e non può chiuderlo. |
| Bundle | Mai link simbolici (un link a un file segreto non entra), niente binari, cache, file > 100 KB; totale max 400 KB (Firestore tiene 1 MiB a documento). |

**Cosa resta aperto, da decidere prima di accenderlo in produzione:** il codice scritto da Claude
Code gira nel container del worker, che ha rete e può chiedere un token al metadata server di Google
con il service account del worker (lo stesso che legge Firestore, cioè i dati dei clienti). L'utente
separato non lo impedisce. Le strade:

1. un servizio Cloud Run separato solo per le build, con un service account **senza ruoli** e senza
   segreti tranne `ANTHROPIC_API_KEY`;
2. oppure accettare il rischio per i soli prodotti in elenco, con Luigi che rivede sempre il risultato
   prima del cliente (già così oggi).

Finché non si decide, consiglio di lasciarlo spento su Cloud Run e provarlo sul laptop.

## Come accenderlo

**Sul laptop** (serve Node.js e la CLI: `npm install -g @anthropic-ai/claude-code`):

```bash
export CHIARA_ENGINE=claude_code
export ANTHROPIC_API_KEY=...            # da .env, mai nel codice
export CHIARA_CLAUDE_CODE_ALLOW_SAME_USER=1
python -m scripts.run_pipeline_cli --request "Un chatbot Streamlit per uno studio yoga" --provider anthropic
```

Su Windows `CHIARA_CLAUDE_CODE_ALLOW_SAME_USER=1` è obbligatorio (non c'è il cambio di utente).

**Su Cloud Run**, nel `.env`:

```
CHIARA_ENGINE=claude_code
ANTHROPIC_API_KEY=...                  # già tra i secret del worker
PIPELINE_RUN_TIMEOUT=840               # la build da sola può prendere 7 minuti
CHIARA_CLAUDE_CODE_BUDGET_USD=2.00     # facoltativo
CHIARA_CLAUDE_CODE_PRODUCTS=chatbot_app,weather_dashboard   # facoltativo
CHIARA_CLAUDE_CODE_MODEL=sonnet        # facoltativo
```

Poi `scripts/deploy_cloudrun.sh --dry-run` e il deploy vero. Con `CHIARA_ENGINE=claude_code` il
deploy costruisce l'immagine del worker con Node.js, la CLI (versione fissata a 2.1.318 in
`gateway/Dockerfile.worker`) e l'utente `builder`; senza, l'immagine resta quella di prima.
Consiglio anche `--memory 2Gi` per il worker (oggi 1Gi): CLI Node + pipeline Python insieme.

## Costi

Una build è una sessione agentica, non una chiamata: tipicamente da pochi centesimi a qualche
dollaro, con il tetto di `CHIARA_CLAUDE_CODE_BUDGET_USD`. Il costo vero compare nei passi
(`[Chiara] ... via claude-code (5 files, tests passed, $0.84)`) e in testa al bundle. Su un
prodotto da 9.90 € il margine va controllato: Marco non lo legge ancora da solo.

## Cosa è stato provato e cosa no

- 38 test offline nuovi (`tests/test_chiara_claude_code.py`, `tests/test_unpack_bundle.py`) + 6 su
  immagine e deploy: la CLI è sostituita da un finto che scrive i file.
- **CLI vera 2.1.318 con chiave finta:** accetta tutti i flag usati e restituisce il JSON atteso
  (`is_error`, `result`, `total_cost_usd`); il motore fa fallback con
  `exit 1: Invalid API key`.
- **Cambio di utente vero** (`builder`) in questo container: CLI avviata come `builder`, cartella e
  home assegnate, `/proc` del worker non leggibile.
- **Non provato:** una build vera con un modello (nessuna chiave Anthropic nel container), la build
  dell'immagine Docker (niente Docker qui; la versione di Node di Debian è la 18), il worker su
  Cloud Run.
