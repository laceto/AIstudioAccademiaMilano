import os
import streamlit as st
from datetime import datetime

st.title("👩‍⚕️ Studio Digitale — Dott.ssa Fabrizia Aceto")
st.caption("Diabetologa & Endocrinologa · Medico moderno che usa le API")
st.markdown("---")

# ── Stato credenziali ──────────────────────────────────────────────────────────
openai_ok  = bool(os.getenv("OPENAI_API_KEY"))
tg_ok      = bool(os.getenv("TELEGRAM_API_ID") and os.getenv("TELEGRAM_API_HASH"))
drive_ok   = os.path.exists("credentials.json")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Oggi", datetime.now().strftime("%d %b %Y"))
c2.metric("OpenAI",       "✅ OK" if openai_ok  else "❌ mancante")
c3.metric("Telegram",     "✅ OK" if tg_ok      else "❌ mancante")
c4.metric("Google Drive", "✅ OK" if drive_ok   else "❌ mancante")

if not openai_ok:
    st.warning(
        "**OpenAI API Key non trovata.** "
        "Alcune funzioni AI non saranno disponibili. "
        "Aggiungi `OPENAI_API_KEY=sk-...` al file `.env` e riavvia."
    )

st.markdown("---")

# ── Strumenti disponibili ──────────────────────────────────────────────────────
st.subheader("🧰 Strumenti disponibili")

col_a, col_b, col_c, col_d = st.columns(4)

with col_a:
    st.markdown("### 🛰️ Research Radar")
    st.markdown(
        "Cerca in **5 database medici** in parallelo:\n"
        "OpenAlex · Semantic Scholar · Europe PMC · CrossRef · ClinicalTrials\n\n"
        "**Nessuna API key richiesta.**"
    )
    st.success("Sempre disponibile")
    if st.button("Apri Research Radar →", use_container_width=True):
        st.switch_page("pages/radar.py")

with col_b:
    st.markdown("### 🔬 PubMed AI")
    st.markdown(
        "Ricerca PubMed con **analisi GPT-4o** per ogni paper:\n"
        "summary clinico · key findings · livello evidenza · sintesi letteratura"
    )
    st.info("Richiede OpenAI API Key")
    if st.button("Apri PubMed AI →", use_container_width=True):
        st.switch_page("pages/pubmed.py")

with col_c:
    st.markdown("### 📊 Meta-Analysis")
    st.markdown(
        "Pipeline completa: cerca paper → **GPT-4o estrae le statistiche** → "
        "DerSimonian-Laird random effects → **forest plot** + funnel plot → report PRISMA."
    )
    st.info("Richiede OpenAI API Key")
    if st.button("Apri Meta-Analysis →", use_container_width=True):
        st.switch_page("pages/meta.py")

with col_d:
    st.markdown("### 👤 Avatar & Community")
    st.markdown(
        "Organizza **chat Telegram/WhatsApp**, genera bozze risposte e post LinkedIn "
        "nel tuo stile. Sync automatico su **Google Drive**."
    )
    st.info("Richiede OpenAI + opz. Telegram/Drive")
    if st.button("Apri Avatar →", use_container_width=True):
        st.switch_page("pages/avatar.py")

st.markdown("---")

# ── Setup rapido ───────────────────────────────────────────────────────────────
with st.expander("⚙️ Setup credenziali (prima configurazione)", expanded=not openai_ok):
    st.markdown("""
**1. OpenAI API Key** (obbligatoria per PubMed AI e Avatar):
```bash
echo "OPENAI_API_KEY=sk-..." >> .env
```

**2. Telegram** (opzionale — per leggere gruppi medici):
- Vai su [my.telegram.org](https://my.telegram.org) → My Applications → crea app
- Copia API_ID e API_HASH nel file `.env`
```bash
echo "TELEGRAM_API_ID=12345678"       >> .env
echo "TELEGRAM_API_HASH=abc123..."    >> .env
```

**3. Google Drive** (opzionale — per salvare digest e bozze):
- [console.cloud.google.com](https://console.cloud.google.com) → Abilita Drive API
- Crea credenziali OAuth2 desktop → scarica `credentials.json` in questa cartella

**Poi riavvia l'app** con `streamlit run app.py`
    """)

st.markdown("---")
st.caption(
    "Tutti gli strumenti di ricerca usano API **100% gratuite** (OpenAlex, Semantic Scholar, "
    "Europe PMC, CrossRef, ClinicalTrials.gov, NCBI PubMed). "
    "L'AI di analisi usa OpenAI GPT-4o (a pagamento). "
    "*Non sostituisce la valutazione clinica professionale.*"
)
