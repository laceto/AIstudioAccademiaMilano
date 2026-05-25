# Psy-Assist

AI assistant for psychologists — 3 tools in a single Streamlit app.

## What it does

| Tab | Input | Output |
|-----|-------|--------|
| Note Sessione | Free-text session summary + patient code | Structured SOAP note (Soggettivo, Obiettivo, Valutazione, Piano) |
| Compiti Terapeutici | Session theme + approach + patient level | 3 personalised therapeutic exercises (CBT/ACT/mindfulness) |
| Psicoeducazione | Topic + target audience | Patient-facing psychoeducation sheet (~400 words) |

All outputs are downloadable as `.txt` files.

## Why psychologists need this in the AI era

- **Documentation overload**: therapists spend 1-2h/day on session notes. SOAP generator cuts this to 2 minutes.
- **Between-session support**: homework exercises give patients structured practice without extra preparation time.
- **Psychoeducation**: personalised handouts used to take 30+ minutes to write; now instant.

## Setup

```bash
cd deliverables/2026-05-25_018_psy-assist
pip install -r requirements.txt

# Set your key in repo .env:
# ANTHROPIC_API_KEY=sk-ant-...

streamlit run app.py
```

## Streamlit Cloud deploy

1. Push to GitHub
2. New app → `deliverables/2026-05-25_018_psy-assist/app.py`
3. Add `ANTHROPIC_API_KEY` in Secrets

## Model

`claude-haiku-4-5-20251001` — fast, cheap (~$0.0003/request), excellent Italian clinical quality.

---

*Psy-Assist · AI Studio Accademia Milano — strumento di supporto professionale, non sostituisce la valutazione clinica.*
