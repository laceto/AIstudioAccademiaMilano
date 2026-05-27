---
request_id: "F004"
date: "2026-05-27"
company: "diabetologia-endocrinologia"
founder: "Fabrizia Aceto"
intent: meta_analysis_engine
outcome: success
price_eur: 19.90
agents_invoked:
  - name: Chiara
    role: implementazione
    action: "statistics.py (DL random effects) + ai_extractor.py (GPT-4o) + visualizer.py (forest/funnel plotly) + streamlit 4-step pipeline"
    status: success
  - name: Compliance Agent
    role: sicurezza
    action: "Disclaimer PRISMA presente, no PII, output richiede verifica full-text prima pubblicazione"
    status: success
skills_used:
  - desimonian_laird_random_effects
  - inverse_variance_fixed_effects
  - egger_publication_bias_test
  - gpt4o_stats_extractor
  - forest_plot_plotly
  - funnel_plot_plotly
  - prisma_report_generator
deliverable: "deliverables/meta-analysis/"
files:
  - statistics.py
  - ai_extractor.py
  - visualizer.py
  - streamlit_app.py
  - requirements.txt
learning_flags:
  new_skills:
    - desimonian_laird_random_effects
    - egger_test
    - gpt4o_stats_extractor
    - forest_plot_plotly
    - prisma_report_generator
  new_mcp: []
  new_pricing:
    meta_analysis_engine: "19.90"
  risk_score: 1
notes: >
  Pipeline 4-step: (1) carica paper da PubMed/JSON/manuale → (2) GPT-4o estrae
  effect size, CI, n, tipo studio per ogni abstract → (3) DerSimonian-Laird
  random effects, I², tau², Q, Egger test, forest plot + funnel plot interattivi
  → (4) report PRISMA in Markdown. Supporta MD/SMD/OR/RR/HR.
  Integrato nel master hub come 4a pagina (pages/meta.py).
---

# F004 — Meta-Analysis Engine

**Deliverable:** `deliverables/meta-analysis/`
**Stack:** numpy + scipy + plotly + OpenAI GPT-4o + Streamlit

## Pipeline

```
Paper (PubMed / JSON / manuale)
        ↓
GPT-4o: estrae effect size, CI, n, tipo studio
        ↓
DerSimonian-Laird random effects
• I² heterogeneity
• Q test (Cochran)
• τ² between-study variance
• Egger test (publication bias)
        ↓
Forest plot (interattivo, Plotly)
Funnel plot (interattivo, Plotly)
        ↓
Report PRISMA in Markdown
```

## Misure di effetto supportate

| Misura | Uso tipico in diabetologia |
|--------|---------------------------|
| MD | ΔHbA1c (%), ΔPeso (kg), ΔGlicemia |
| SMD | Outcome su scale diverse |
| OR | Eventi cardiovascolari, ipoglicemia |
| RR | Rischio relativo eventi |
| HR | Mortalità, end-point time-to-event |

## Avvio

```bash
cd aziende-fabrizia/diabetologia-endocrinologia
streamlit run app.py   # → pagina Meta-Analysis nella sidebar
```
