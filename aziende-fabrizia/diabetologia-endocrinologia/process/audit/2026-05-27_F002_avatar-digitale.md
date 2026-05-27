---
request_id: "F002"
date: "2026-05-27"
company: "diabetologia-endocrinologia"
founder: "Fabrizia Aceto"
intent: avatar_digitale_community
outcome: success
price_eur: 19.90
agents_invoked:
  - name: Chiara
    role: implementazione
    action: "Telegram reader + chat organizer + avatar persona + gdrive sync + Streamlit dashboard"
    status: success
  - name: Compliance Agent
    role: sicurezza
    action: "No PII nel codice, disclaimer su ogni output AI, token mai committati"
    status: success
skills_used:
  - telethon_reader
  - whatsapp_parser
  - chat_categorizer
  - avatar_persona
  - gdrive_sync
  - streamlit_frontend
deliverable: "deliverables/avatar-digitale/"
files:
  - telegram_reader.py
  - chat_organizer.py
  - avatar_persona.py
  - gdrive_sync.py
  - streamlit_app.py
  - requirements.txt
  - .env.example
learning_flags:
  new_skills:
    - telethon_reader
    - chat_categorizer
    - avatar_persona
    - gdrive_sync
  new_mcp: []
  new_pricing:
    avatar_digitale_community: "19.90"
  risk_score: 2
notes: >
  Sistema avatar a 4 layer: Telegram live (Telethon MTProto) + WhatsApp export parser →
  GPT-4o categorizzazione per topic clinico → avatar che risponde in voce di Fabrizia →
  sync Google Drive (digest, snapshot, bozze). 5 tab Streamlit.
  Risk score 2: Telegram richiede credenziali OAuth utente (API ID/Hash), gestite localmente.
  credentials.json e token.json Drive mai committati (.gitignore).
---

# F002 — Avatar Digitale Fabrizia

**Deliverable:** `deliverables/avatar-digitale/`  
**Stack:** Telethon + WhatsApp parser + OpenAI GPT-4o + Google Drive API + Streamlit  
**Prezzo:** €19.90

## Architettura

```
INPUT
├── Telegram (Telethon — MTProto ufficiale, gratuito)
└── WhatsApp (export .txt — parser regex)

PROCESSING
├── chat_organizer.py   → categorizza per topic clinico (GPT-4o)
├── avatar_persona.py   → risponde nel tono di Fabrizia
└── generate_daily_digest() → digest Markdown giornaliero

STORAGE
└── gdrive_sync.py → Google Drive (Digest / Snapshots / Bozze Post)

UI
└── streamlit_app.py → 5 tab dashboard
```

## Come avviare

```bash
cd aziende-fabrizia/diabetologia-endocrinologia/deliverables/avatar-digitale
cp .env.example .env    # compila con le tue credenziali
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Setup credenziali (una tantum)

**Telegram:**
1. Vai su https://my.telegram.org → My Applications
2. Crea app → copia API_ID e API_HASH → metti in .env
3. Prima esecuzione: inserisci numero telefono + codice OTP
4. Sessione salvata in `fabrizia.session` — non committare

**Google Drive:**
1. console.cloud.google.com → nuovo progetto → abilita Drive API
2. Credenziali → OAuth2 desktop → scarica `credentials.json`
3. Prima esecuzione: autorizzazione browser → salva `token.json`
4. `credentials.json` e `token.json` mai committati
