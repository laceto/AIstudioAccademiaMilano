---
request_id: "F003"
date: "2026-05-27"
company: "diabetologia-endocrinologia"
founder: "Fabrizia Aceto"
intent: research_radar_app
outcome: success
price_eur: 14.90
agents_invoked:
  - name: Chiara
    role: implementazione
    action: "5 source fetcher + aggregatore parallelo + Streamlit 4-tab dashboard"
    status: success
  - name: Compliance Agent
    role: sicurezza
    action: "Nessuna API key richiesta, disclaimer presente, no PII"
    status: success
skills_used:
  - openalex_fetcher
  - semantic_scholar_fetcher
  - europe_pmc_fetcher
  - crossref_fetcher
  - clinical_trials_fetcher
  - parallel_aggregator
  - streamlit_frontend
deliverable: "deliverables/research-radar/"
files:
  - sources/openalex.py
  - sources/semantic_scholar.py
  - sources/europe_pmc.py
  - sources/clinical_trials.py
  - sources/crossref.py
  - aggregator.py
  - streamlit_app.py
  - requirements.txt
learning_flags:
  new_skills:
    - openalex_fetcher
    - semantic_scholar_fetcher
    - europe_pmc_fetcher
    - clinical_trials_fetcher
    - crossref_fetcher
    - parallel_aggregator
  new_mcp: []
  new_pricing:
    research_radar_app: "14.90"
  risk_score: 1
notes: >
  5 API 100% gratuite interrogate in parallelo (ThreadPoolExecutor).
  Deduplicazione per DOI + fingerprint titolo. 4 tab: ricerca multi-fonte,
  trial clinici attivi, trend/concetti OpenAlex, journal watch CrossRef.
  Solo 2 dipendenze: streamlit + requests. Zero API key.
---

# F003 — Research Radar

**Deliverable:** `deliverables/research-radar/`
**Dipendenze:** `streamlit`, `requests` — nient'altro
**API key richieste:** nessuna

## Fonti integrate (tutte gratuite)

| Fonte | Specialità | Limite |
|-------|-----------|--------|
| **OpenAlex** | 250M+ works, trend, concetti, citazioni | 100k req/giorno |
| **Semantic Scholar** | AI-ranked, influential citations, TLDR auto | 100 req/min |
| **Europe PMC** | PubMed + EU + preprint + grants | nessuno |
| **CrossRef** | DOI, journal impact, 100M+ record | nessuno (polite pool) |
| **ClinicalTrials.gov** | Trial attivi/completati, reclutamento pazienti | nessuno |

## Avvio

```bash
cd aziende-fabrizia/diabetologia-endocrinologia/deliverables/research-radar
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## 4 Tab

1. **Ricerca Multi-fonte** — query unica → 4 DB in parallelo → deduplicato, ordinato per citazioni
2. **Trial Clinici** — ClinicalTrials.gov con filtri stato/fase/intervento
3. **Trend & Concetti** — OpenAlex: grafico pubblicazioni/anno + top concetti associati
4. **Journal Watch** — CrossRef: ultimi articoli da Diabetes Care, Diabetologia, Lancet D&E, JCEM, NEJM, Thyroid
