"""
Meta-Analysis Engine — Dott.ssa Fabrizia Aceto
Pipeline completa: ricerca → estrazione AI → calcolo → forest plot → report PRISMA.
"""
import os, sys, json
import streamlit as st
from openai import OpenAI
from datetime import datetime

# Permette import dai deliverable adiacenti quando lanciato standalone
_ROOT = os.path.dirname(os.path.dirname(__file__))
for sub in ("pubmed-researcher", "research-radar"):
    p = os.path.join(_ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from statistics  import prepare_study, run as meta_run, egger_test
from ai_extractor import batch_extract, generate_prisma_report
from visualizer  import forest_plot, funnel_plot

st.set_page_config(page_title="Meta-Analysis · Fabrizia", page_icon="📊", layout="wide")

st.title("📊 Meta-Analysis Engine")
st.caption("Pipeline completa: ricerca → estrazione AI → calcolo DerSimonian-Laird → forest plot → report PRISMA")

with st.sidebar:
    api_key = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY",""), type="password")
    method  = st.radio("Metodo statistico",
                       ["random_effects","fixed_effects"],
                       format_func=lambda x: "🎲 Random Effects (DL)" if x=="random_effects" else "📌 Fixed Effects (IV)")
    st.markdown("---")
    st.caption("**Misure di effetto**")
    st.caption("• MD — Mean Difference (es. ΔHbA1c)")
    st.caption("• SMD — Standardized MD (scale diverse)")
    st.caption("• OR — Odds Ratio (eventi binari)")
    st.caption("• RR — Risk Ratio")
    st.caption("• HR — Hazard Ratio (time-to-event)")

# ── Step tracker ───────────────────────────────────────────────────────────────
STEPS = ["1. Carica paper", "2. Estrai statistiche", "3. Meta-analisi", "4. Report"]
current_step = st.session_state.get("ma_step", 0)
cols_step = st.columns(4)
for i, (col, label) in enumerate(zip(cols_step, STEPS)):
    col.markdown(
        f"<div style='text-align:center;padding:6px;border-radius:6px;"
        f"background:{'#dbeafe' if i==current_step else '#f8fafc'};'>"
        f"<b>{'→ ' if i==current_step else ''}{label}</b></div>",
        unsafe_allow_html=True,
    )
st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — CARICA PAPER
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("📥 Step 1 — Carica i paper", expanded=(current_step == 0)):
    source = st.radio("Sorgente paper", ["Ricerca PubMed live", "Importa da Research Radar (JSON)", "Inserisci manualmente"], horizontal=True)

    if source == "Ricerca PubMed live":
        try:
            from pubmed_fetcher import search_pubmed, fetch_papers
            q_pub = st.text_input("Query PubMed", placeholder="es. GLP-1 diabetes HbA1c randomized controlled trial")
            c1, c2 = st.columns(2)
            n_pub  = c1.slider("Max articoli", 5, 50, 20)
            y_pub  = c2.number_input("Da anno", 2010, 2026, 2018)
            if st.button("🔍 Cerca su PubMed", type="primary") and q_pub:
                with st.spinner("Ricerca PubMed..."):
                    pmids  = search_pubmed(q_pub, max_results=n_pub, date_range=(f"{y_pub}/01/01","2099/12/31"))
                    papers = fetch_papers(pmids)
                st.session_state["ma_papers"] = papers
                st.session_state["ma_query"]  = q_pub
                st.session_state["ma_step"]   = 1
                st.success(f"Caricati {len(papers)} paper — vai allo Step 2")
        except ImportError:
            st.error("Modulo pubmed_fetcher non trovato. Usa Importa JSON o Manuale.")

    elif source == "Importa da Research Radar (JSON)":
        st.caption("Dal Research Radar, esporta i risultati in CSV, poi convertili o carica un JSON manuale.")
        uploaded = st.file_uploader("Carica JSON (lista di paper)", type="json")
        if uploaded:
            papers = json.load(uploaded)
            st.session_state["ma_papers"] = papers
            st.session_state["ma_step"]   = 1
            st.success(f"Caricati {len(papers)} paper")

    else:  # Manuale
        st.info("Inserisci direttamente i dati nello Step 2 (editor manuale).")
        if st.button("Vai a inserimento manuale →"):
            st.session_state["ma_papers"] = []
            st.session_state["ma_step"]   = 1

    if "ma_papers" in st.session_state:
        st.success(f"**{len(st.session_state['ma_papers'])} paper pronti** per l'estrazione.")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — ESTRAI STATISTICHE
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("🤖 Step 2 — Estrazione statistiche (AI)", expanded=(current_step == 1)):
    outcome = st.text_input(
        "Outcome di interesse",
        placeholder="es. HbA1c reduction (%), body weight (kg), cardiovascular events",
        help="L'AI cercherà questo outcome specifico in ogni abstract.",
    )

    col_e1, col_e2 = st.columns([2, 1])
    with col_e1:
        if st.button("🧠 Estrai con GPT-4o", type="primary",
                     disabled=(not api_key or not outcome or "ma_papers" not in st.session_state)):
            papers = st.session_state["ma_papers"]
            client = OpenAI(api_key=api_key)

            prog = st.progress(0, "Estrazione statistiche in corso...")
            def _cb(i, total):
                prog.progress(i / total, f"Paper {i}/{total}")

            extractable, skipped = batch_extract(papers, outcome, client, progress_callback=_cb)
            prog.empty()

            st.session_state["ma_extractable"] = extractable
            st.session_state["ma_skipped"]     = skipped
            st.session_state["ma_outcome"]     = outcome
            st.session_state["ma_step"]        = 2

    with col_e2:
        st.markdown("**Oppure: aggiungi studio manualmente**")

    # Editor manuale
    with st.form("manual_study"):
        st.caption("Aggiungi studio manuale (quando l'abstract non ha i dati ma hai il full-text)")
        c1, c2 = st.columns(2)
        m_name  = c1.text_input("Nome studio", placeholder="Autore et al. (2023)")
        m_type  = c2.selectbox("Tipo", ["RCT","cohort","caso-controllo","altro"])
        c3,c4,c5 = st.columns(3)
        m_n     = c3.number_input("n totale", 0, 100000, 0)
        m_nt    = c4.number_input("n trattamento", 0, 100000, 0)
        m_nc    = c5.number_input("n controllo", 0, 100000, 0)
        c6,c7   = st.columns(2)
        m_em    = c6.selectbox("Misura effetto", ["MD","SMD","OR","RR","HR"])
        m_es    = c7.number_input("Effect size", value=0.0, format="%.4f")
        c8,c9   = st.columns(2)
        m_cil   = c8.number_input("CI inferiore", value=0.0, format="%.4f")
        m_ciu   = c9.number_input("CI superiore", value=0.0, format="%.4f")
        m_out   = st.text_input("Outcome", placeholder="HbA1c reduction")
        m_notes = st.text_input("Note", placeholder="24 settimane, ITT")
        if st.form_submit_button("➕ Aggiungi studio"):
            manual = {
                "extractable": True, "study_name": m_name, "study_type": m_type,
                "n_total": m_n, "n_treatment": m_nt, "n_control": m_nc,
                "effect_measure": m_em, "effect_size": m_es,
                "ci_lower": m_cil, "ci_upper": m_ciu,
                "outcome": m_out, "notes": m_notes,
            }
            if "ma_extractable" not in st.session_state:
                st.session_state["ma_extractable"] = []
            st.session_state["ma_extractable"].append(manual)
            st.success(f"Aggiunto: {m_name}")

    # Mostra risultati estrazione
    if "ma_extractable" in st.session_state:
        ext  = st.session_state["ma_extractable"]
        skip = st.session_state.get("ma_skipped", [])
        st.success(f"✅ **{len(ext)} studi estraibili** | ❌ {len(skip)} esclusi")

        if ext:
            st.markdown("**Studi inclusi:**")
            for s in ext:
                em  = s.get("effect_measure","?")
                es  = s.get("effect_size","?")
                cil = s.get("ci_lower","?")
                ciu = s.get("ci_upper","?")
                st.markdown(
                    f"• **{s.get('study_name','?')}** ({s.get('study_type','?')}, n={s.get('n_total','?')}) "
                    f"— {em}: {es} [{cil}, {ciu}] | {s.get('outcome','?')}"
                )
        if skip:
            with st.expander(f"Studi esclusi ({len(skip)})"):
                for s in skip:
                    st.caption(f"• {s.get('study_name','?')} — {s.get('reason','?')}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — META-ANALISI
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("📊 Step 3 — Calcolo & Visualizzazioni", expanded=(current_step == 2)):
    if "ma_extractable" not in st.session_state or not st.session_state["ma_extractable"]:
        st.info("Completa lo Step 2 prima.")
    else:
        ext    = st.session_state["ma_extractable"]
        effect_label = st.text_input("Etichetta asse X", value=st.session_state.get("ma_outcome","Effect Size"))

        if st.button("⚙️ Esegui Meta-Analisi", type="primary"):
            prepared = [prepare_study(s) for s in ext]
            result   = meta_run(prepared, method=method)

            if result.get("error"):
                st.error(result["error"])
            else:
                egger = egger_test(prepared)
                st.session_state["ma_result"]   = result
                st.session_state["ma_prepared"] = [p for p in prepared if p]
                st.session_state["ma_egger"]    = egger
                st.session_state["ma_step"]     = 3

        if "ma_result" in st.session_state:
            r = st.session_state["ma_result"]

            # ── Metriche principali ───────────────────────────────────────────
            m1,m2,m3,m4,m5 = st.columns(5)
            m1.metric("Studi (k)",        r["k"])
            m2.metric("Stima pooled",     f"{r['estimate']:.3f}")
            m3.metric("95% CI",           f"[{r['ci_lower']:.3f}, {r['ci_upper']:.3f}]")
            m4.metric("p-value",          f"{r['p_value']:.4f}")
            m5.metric("I²",               f"{r['I2']:.1f}%", delta=r["heterogeneity"], delta_color="off")

            col_q1, col_q2, col_q3 = st.columns(3)
            col_q1.metric("Q",   f"{r['Q']:.2f}")
            col_q2.metric("p(Q)", f"{r['p_heterogeneity']:.4f}")
            col_q3.metric("τ²",  f"{r['tau2']:.4f}")

            # Egger
            egger = st.session_state.get("ma_egger", {})
            if not egger.get("error"):
                st.caption(f"**Test di Egger:** {egger['bias']} (intercetta={egger['intercept']:.3f}, p={egger['p_value']:.3f})")

            st.markdown("---")

            # ── Forest plot ────────────────────────────────────────────────────
            st.markdown("### Forest Plot")
            null_val = 1.0 if r["log_scale"] else 0.0
            fig_f = forest_plot(
                st.session_state["ma_prepared"], r,
                effect_label=effect_label,
                null_value=null_val,
            )
            st.plotly_chart(fig_f, use_container_width=True)

            # ── Funnel plot ────────────────────────────────────────────────────
            st.markdown("### Funnel Plot (Publication Bias)")
            fig_fn = funnel_plot(
                st.session_state["ma_prepared"], r,
                effect_label=effect_label,
                egger=egger,
            )
            st.plotly_chart(fig_fn, use_container_width=True)

            # ── Tabella dettaglio ──────────────────────────────────────────────
            with st.expander("Tabella studi"):
                import pandas as pd
                rows = []
                for s, w in zip(st.session_state["ma_prepared"], r["study_weights"]):
                    log_s = r["log_scale"]
                    _b = lambda x: round(float(__import__("numpy").exp(x)),3) if log_s else round(float(x),3)
                    rows.append({
                        "Studio":       s.get("study_name","?"),
                        "n":            s.get("n_total","?"),
                        "Tipo":         s.get("study_type","?"),
                        "Effetto":      _b(s["_log_es"]),
                        "CI inf":       _b(s["_log_ci_l"]),
                        "CI sup":       _b(s["_log_ci_u"]),
                        "SE":           round(s["_se"],4),
                        "Peso (%)":     round(w,1),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — REPORT PRISMA
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("📝 Step 4 — Report PRISMA", expanded=(current_step == 3)):
    if "ma_result" not in st.session_state:
        st.info("Completa lo Step 3 prima.")
    elif not api_key:
        st.warning("Inserisci OpenAI API Key per generare il report.")
    else:
        if st.button("📝 Genera report PRISMA", type="primary"):
            client = OpenAI(api_key=api_key)
            with st.spinner("Generazione report..."):
                report = generate_prisma_report(
                    query=st.session_state.get("ma_query",""),
                    outcome=st.session_state.get("ma_outcome",""),
                    total_found=len(st.session_state.get("ma_papers",[])),
                    extractable=st.session_state["ma_extractable"],
                    skipped=st.session_state.get("ma_skipped",[]),
                    meta_result=st.session_state["ma_result"],
                    client=client,
                )
            st.session_state["ma_report"] = report

        if "ma_report" in st.session_state:
            st.markdown(st.session_state["ma_report"])
            st.download_button(
                "⬇️ Scarica report (.md)",
                data=st.session_state["ma_report"],
                file_name=f"meta_analisi_{datetime.now().strftime('%Y%m%d')}_{st.session_state.get('ma_outcome','')[:20]}.md",
                mime="text/markdown",
            )

st.markdown("---")
st.caption(
    "*Meta-analisi basata su dati estratti da abstract con AI — da verificare con full-text prima di pubblicazione. "
    "Non sostituisce la revisione sistematica manuale secondo PRISMA.*"
)
