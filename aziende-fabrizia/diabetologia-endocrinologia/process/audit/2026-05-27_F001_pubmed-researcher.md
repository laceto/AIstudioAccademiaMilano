---
request_id: "F001"
date: "2026-05-27"
company: "diabetologia-endocrinologia"
founder: "Fabrizia Aceto"
intent: pubmed_researcher_app
outcome: success
price_eur: 14.90
agents_invoked:
  - name: Chiara
    role: implementazione
    action: "Streamlit app + PubMed E-utilities wrapper + GPT-4o analyzer"
    status: success
  - name: Compliance Agent
    role: sicurezza
    action: "Disclaimer clinico presente, no PII nel codice"
    status: success
skills_used:
  - pubmed_fetcher
  - ai_analyzer
  - streamlit_frontend
deliverable: "deliverables/pubmed-researcher/"
files:
  - pubmed_fetcher.py
  - ai_analyzer.py
  - streamlit_app.py
  - requirements.txt
learning_flags:
  new_skills:
    - pubmed_fetcher
    - ai_analyzer
  new_mcp: []
  new_pricing:
    pubmed_researcher_app: "14.90"
  risk_score: 1
notes: >
  App a 3 layer: NCBI E-utilities (ufficiale, gratuita) → GPT-4o analisi per paper
  → sintesi letteratura complessiva. 3 tab: lista paper, sintesi, domande cliniche aperte.
  Query rapide pre-caricate per i topic principali di Fabrizia.
  Disclaimer clinico presente in ogni output AI.
---

# F001 — PubMed Researcher

**Deliverable:** `deliverables/pubmed-researcher/`  
**Stack:** NCBI E-utilities + OpenAI GPT-4o + Streamlit  
**Prezzo:** €14.90

## Cosa fa

Fabrizia cerca su PubMed con query booleane avanzate. L'app:
1. Chiama NCBI E-utilities (API ufficiale NIH, gratuita)
2. Scarica abstract, autori, rivista, anno, MeSH terms
3. GPT-4o analizza ogni paper: summary clinica, key findings, implicazioni pratiche, livello di evidenza
4. Genera sintesi complessiva della letteratura per la query
5. Propone 3 domande cliniche aperte per approfondimenti

## Come avviare

```bash
cd aziende-fabrizia/diabetologia-endocrinologia/deliverables/pubmed-researcher
pip install -r requirements.txt
OPENAI_API_KEY=sk-... streamlit run streamlit_app.py
```

## Query suggerite pre-caricate

- GLP-1 agonists HbA1c reduction type 2 diabetes
- continuous glucose monitoring outcomes
- SGLT2 inhibitors cardiovascular benefit
- insulin resistance PCOS treatment
- diabetic neuropathy new treatments 2024
- thyroid nodule management guidelines
- metformin type 2 diabetes first line
- CGM time in range clinical outcomes
