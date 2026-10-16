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

## Cosa NON c'è ancora

- **Team ricerca** (Scout, Analyst, Curator, Reporter): non è per-richiesta. Il piano è un giro settimanale (Cloud Scheduler)
  che scrive un digest letto da Gianni. Da fare.
- **Pablo, Sofia, Carlos**: ruoli di costruzione del gateway, non agenti a runtime; nessun nodo.
- Non provato con un modello vero: i test usano un modello finto che risponde per ruolo (22 test).
- Più revisori = più chiamate: ~7 chiamate veloci per job invece di ~3 (in parallelo: la durata cambia poco, il costo sì).
- Il limite di tempo del worker (`_run_timeout`) non è stato rivisto per v2.

## Test

`pytest tests/test_studio_pipeline_v2.py -v`
