# Pipeline v2 — tutti i ruoli nella pipeline delle richieste

v2 gira **accanto** a v1 (`deliverables/2026-05-25_016_aistudio-langgraph`). Si sceglie con una variabile
d'ambiente sul worker; senza variabile (o con un valore sconosciuto) gira v1, come prima.

```
PIPELINE_VERSION=v2     # sul servizio pipeline-worker di Cloud Run
```

Per tornare indietro: togli la variabile (o `v1`). Nessun dato cambia formato: il risultato del job ha solo due campi in più
(`advisories`, `draft_post`), vuoti con v1.

## Dove entra ogni ruolo

| Quando | Ruolo | Cosa fa | Può bloccare? |
|--------|-------|---------|---------------|
| Prima di tutto | **Lorenzo** | Cerca prompt injection nel testo del cliente | Sì: se trova qualcosa, **o se la scansione non funziona**, la richiesta si ferma (job `failed`, Luigi avvisato) |
| Dopo Gianni | **Devil's Advocate** | Sfida la fascia di prezzo | Solo se il lavoro non ha un prezzo approvato; il prezzo di Luigi non viene mai scavalcato (resta una nota) |
| Dopo Gianni | **Financial Controller** | `adeguatezza = prezzo / (ore × costo orario)`; sotto 0,85 = sottoprezzato | No: nota. Un lavoro gratis non è un difetto |
| Dopo Gianni, solo deploy remoto | **IT Staff** | Nota per Luigi: servono account/credenziali | No (solo consiglio) |
| Dopo Chiara, in parallelo | Technical Auditor, Compliance, Reputation Guardian (v1) + **Quality Reliability Lead**, **API Product Designer**, **Operational Monitor** | Punteggio di rischio 1–5 | Sì, tramite l'aggregatore |
| Aggregatore | (v2) | Media **e** soglia critica: un solo 5 non si perde nella media | Sì → Luigi |
| Se scatta un trigger | **Core Architect** | Rilettura architetturale (modello "smart") | No: nota per Luigi |
| Dopo la consegna | **Valentina** | Bozza di annuncio, senza nome/prezzo/parole del cliente | No: **non pubblica mai** |

Il Core Architect viene chiamato se: QA ha già fallito una volta, oppure il rischio medio è ≥ 2,5, oppure l'adeguatezza del prezzo < 0,85.

Le note (`advisories`) e la bozza (`draft_post`) viaggiano nel risultato del job; nessuno le esegue o le pubblica.

## Numeri da tarare (sono ipotesi)

In `nodes.py`: `COST_PER_HOUR_EUR = 6.0` (costo di un'ora di lavoro dello studio, API comprese), `PRICING_ADEQUACY_MIN = 0.85`,
`ARCHITECT_RISK_THRESHOLD = 2.5`. Vanno ricalibrati sui primi job reali.

## Team ricerca → Gianni

Il team ricerca non lavora per richiesta: una volta a settimana `POST /research/run` sul worker esegue Scout → Analyst → Curator
(senza LLM) e salva i primi 10 repo in un digest (`gateway/research_digest.py`; Firestore `research/latest` su Cloud Run). In v2 Gianni
legge i primi 5 (titolo, punteggio, una riga) in un blocco separato e dichiarato non fidato, solo per scegliere le librerie.
Digest assente, più vecchio di 14 giorni o rovinato = Gianni lavora come in v1 (il trace dice `research=none` / `research=digest`).
Il Reporter (Markdown) non serve qui: il digest è già la sintesi. Runbook: `process/runbook_research_digest.md`.

Il worker ora copia anche questa cartella v2 e `scripts/github_research` (prima l'immagine di `Dockerfile.worker` non conteneva v2:
con `PIPELINE_VERSION=v2` ogni job sarebbe fallito).

## Cosa NON c'è ancora

- **Job Cloud Scheduler del digest**: il codice c'è (vedi sotto) ma la risorsa cloud non è stata creata; il comando `gcloud`
  è in `process/runbook_research_digest.md`. Finché non lo crei, o finché `/research/run` non viene chiamato a mano, non c'è
  nessun digest e Gianni lavora senza.
- **Pablo, Sofia, Carlos**: ruoli di costruzione del gateway, non agenti a runtime; nessun nodo.
- Provato con un modello vero solo con OpenAI (gpt-4o-mini / gpt-4o), non con Anthropic. Vedi le misure qui sotto.

## Misurato con un modello vero (2026-10-16, `scripts/run_v2_smoke.py --live --probe-lorenzo`)

| Lavoro | Versione | Esito | Tempo | Chiamate | Costo ~ |
|--------|----------|-------|-------|----------|---------|
| Report PDF (pulito) | v2 | ok | 12–14 s | 13 | $0.010 |
| Report PDF (pulito) | v1 | ok | 7–11 s | 7 | $0.009 |
| Injection evidente | v2 | fermato da Lorenzo | 0.7–1.0 s | 1 | ~$0 |
| App Streamlit + deploy remoto | v2 | **QA fallita 3 volte** (chiave API scritta nel codice, senza disclaimer) | 21–28 s | 25–27 | $0.02 |

- **Costo**: v2 costa quanto v1 (+4 %), perché la spesa sta nelle chiamate "smart" (Gianni, Chiara); i revisori in più usano il modello piccolo. Le chiamate raddoppiano (7 → 13) e il tempo cresce del 15–80 %.
- **Lorenzo**: 8 prove (4 injection, 4 richieste normali ma "a rischio" come "ignora i messaggi duplicati" o "chiavi API in un vault"): 0 errori. Poche prove: non è una garanzia.
- **Timeout**: il peggiore misurato (3 tentativi di build) è 28 s; il worker aspetta 600 s (`PIPELINE_RUN_TIMEOUT`) e Cloud Tasks 900 s. Margine ampio.
- **Bug trovato e corretto**: dopo un nuovo tentativo di Chiara il pannello di rischio conservava i punteggi della build scartata (6 → 12 → 18 punteggi), quindi un solo 5 vecchio rimandava a Luigi ogni rifacimento. Ora ogni build parte con un pannello nuovo.
- **Soglie, dati alla mano**:
  - `COST_PER_HOUR_EUR = 6.0` è sbagliato per come lo si usa: Gianni stima 2,5 h sia per un PDF da una pagina sia per un'app Streamlit, quindi qualunque prodotto sotto 12,75 € risulta "sottoprezzato" (PDF 1,90 € → 0,13; meteo 9,90 € → 0,66) e il Core Architect (modello "smart") viene chiamato quasi sempre. Il costo vero di un job misurato è 1–2 centesimi. Il valore giusto dipende da cosa significa "costo": decide Luigi; non l'ho cambiato.
  - `ARCHITECT_RISK_THRESHOLD = 2.5` e `PRICING_ADEQUACY_MIN = 0.85`: non valutabili con 3 lavori (nessun rischio medio ha superato 2,0).
  - Il Devil's Advocate ha contestato il prezzo in entrambi i lavori con prezzo (1,90 € e 9,90 €): per un lavoro senza prezzo approvato quasi ogni richiesta andrebbe a Luigi.
- Non misurato: Anthropic come provider; l'app Streamlit con v1 (la QA fallita viene da Chiara/QA di v1, non l'ho confrontata); il doppio messaggio `[RiskPanel]` nella traccia, che c'è anche in v1 (stream del riavvio dopo l'approvazione).
- Le misure qui sotto sono senza digest di ricerca (non ne esisteva uno): con il digest il prompt di Gianni (modello "smart") è più lungo, quindi costo e tempo salgono un po'. La ricerca GitHub vera non è stata chiamata.

## Test

`pytest tests/test_studio_pipeline_v2.py -v`
