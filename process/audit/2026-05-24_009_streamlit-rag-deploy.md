---
request_id: "009"
date: "2026-05-24"
intent: chatbot_creation
intent_subtype: deploy_existing_app
product_sku: chatbot_app
price: 19.90
currency: EUR
outcome: success
agents_invoked:
  - {name: Stacy, role: intent_classification, action: classified chatbot_creation/deploy_existing_app, duration_sec: 34, status: pass}
  - {name: Gianni, role: technical_scoping, action: identified sys.path fix + kitai wheel + vectorstore blockers, duration_sec: 117, status: pass}
  - {name: Chiara, role: implementation, action: created requirements.txt + sys.path patch + .streamlit/README.md, duration_sec: 100, status: pass}
  - {name: Stacy, role: qa_validation, action: qa pass with 3 warnings (all resolved), duration_sec: 41, status: pass}
  - {name: Marco, role: financial_processing, action: INV-009 EUR 19.90 approved, duration_sec: 44, status: pass}
  - {name: Francesca, role: delivery, action: git push + audit log, duration_sec: TBD, status: in_progress}
skills_used:
  - streamlit_cloud_deploy
  - openai_api_integration
  - streamlit_secrets_handling
learning_flags:
  new_skills:
    - streamlit_cloud_local_wheel_deploy
  new_mcp: []
  risk_score: 1
notes: |
  kitai installed via HTTPS URL to wheel in repo root (not PyPI).
  Vectorstore committed at data/vectorstore/feeds/ — no rebuild needed on cold start.
  OPENAI_API_KEY must be set manually in Streamlit Cloud Secrets by Luigi.
  Ongoing per-query OpenAI cost: ~EUR 0.005–0.015 (monitor at platform.openai.com/account/usage).
  Stacy warnings (W2, W3): kitai wheel URL is floating (raw/main); no version pins on langchain/openai.
  Both acceptable for initial deploy; recommend pinning before production hardening.
---

# Request 009 — Streamlit RAG Chatbot Cloud Deploy

Deploy `output/chatbot_rag.py` from `laceto/rss_feed` to Streamlit Community Cloud.

## Delivered artifacts

| Artifact | Location | Status |
|---|---|---|
| `requirements.txt` | `laceto/rss_feed` root | Committed + pushed |
| `sys.path` import fix | `output/chatbot_rag.py` lines 1-2 | Committed + pushed |
| `.streamlit/README.md` | `laceto/rss_feed/.streamlit/` | Committed + pushed |
| `.gitignore` patch | `laceto/rss_feed` root | Committed + pushed |

## Remaining manual step (Luigi)

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app** → connect `laceto/rss_feed`
3. Set **Main file path**: `output/chatbot_rag.py`
4. Under **Advanced settings > Secrets**, paste:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
5. Click **Deploy** — cold start ~60–90s (FAISS index load)

## Invoice

INV-009 | EUR 19.90 | 2026-05-24
