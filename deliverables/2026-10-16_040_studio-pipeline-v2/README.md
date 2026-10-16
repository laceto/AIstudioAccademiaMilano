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
- Non provato con un modello vero: i test usano un modello finto che risponde per ruolo (56 test v2 + digest). Anche la ricerca GitHub vera non è stata chiamata.
- Più revisori = più chiamate: ~7 chiamate veloci per job invece di ~3 (in parallelo: la durata cambia poco, il costo sì).
- Il limite di tempo del worker (`_run_timeout`) non è stato rivisto per v2.

## Test

`pytest tests/test_studio_pipeline_v2.py -v`
