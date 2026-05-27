import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deliverables', 'meta-analysis'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deliverables', 'pubmed-researcher'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deliverables', 'research-radar'))

import json
import streamlit as st
from openai import OpenAI
from datetime import datetime

from statistics    import prepare_study, run as meta_run, egger_test
from ai_extractor  import batch_extract, generate_prisma_report
from visualizer    import forest_plot, funnel_plot

st.title("📊 Meta-Analysis Engine")
st.caption("Pipeline: ricerca → estrazione AI → DerSimonian-Laird → forest plot → report PRISMA")

with st.sidebar:
    api_key = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY",""), type="password")
    method  = st.radio("Metodo",
                       ["random_effects","fixed_effects"],
                       format_func=lambda x: "🎲 Random Effects (DL)" if x=="random_effects" else "📌 Fixed Effects (IV)")
    st.markdown("---")
    st.caption("**Pipeline in 4 step:**")
    st.caption("1. Carica paper (PubMed o JSON)")
    st.caption("2. GPT-4o estrae le statistiche")
    st.caption("3. Calcolo meta-analisi + plot")
    st.caption("4. Report PRISMA in Markdown")
    st.markdown("---")
    st.caption("**Misure di effetto:**")
    for m in ["MD — Mean Difference","SMD — Standardized MD","OR — Odds Ratio","RR — Risk Ratio","HR — Hazard Ratio"]:
        st.caption(f"• {m}")

# Step indicator
STEPS = ["1 Carica", "2 Estrai", "3 Calcola", "4 Report"]
step  = st.session_state.get("ma_step", 0)
cols  = st.columns(4)
for i,(c,l) in enumerate(zip(cols,STEPS)):
    c.markdown(
        f"<div style='text-align:center;padding:5px;border-radius:6px;"
        f"background:{'#dbeafe' if i==step else '#f8fafc'};font-size:.85rem'>"
        f"<b>{l}</b></div>", unsafe_allow_html=True)
st.markdown("---")

# ── STEP 1 ─────────────────────────────────────────────────────────────────────
with st.expander("📥 Step 1 — Carica paper", expanded=(step==0)):
    src = st.radio("Sorgente", ["PubMed live","JSON","Manuale"], horizontal=True)
    if src == "PubMed live":
        try:
            from pubmed_fetcher import search_pubmed, fetch_papers
            q   = st.text_input("Query PubMed", placeholder="GLP-1 diabetes HbA1c randomized")
            c1,c2 = st.columns(2)
            n   = c1.slider("Max articoli", 5, 50, 20)
            y   = c2.number_input("Da anno", 2010, 2026, 2018)
            if st.button("🔍 Cerca", type="primary") and q:
                with st.spinner():
                    pmids  = search_pubmed(q, max_results=n, date_range=(f"{y}/01/01","2099/12/31"))
                    papers = fetch_papers(pmids)
                st.session_state.update({"ma_papers":papers,"ma_query":q,"ma_step":1})
                st.success(f"{len(papers)} paper caricati → vai allo Step 2")
        except ImportError:
            st.error("pubmed_fetcher non trovato. Usa JSON o Manuale.")

    elif src == "JSON":
        up = st.file_uploader("Carica JSON", type="json")
        if up:
            papers = json.load(up)
            st.session_state.update({"ma_papers":papers,"ma_step":1})
            st.success(f"{len(papers)} paper caricati")

    else:
        if st.button("Inserisci manualmente →"):
            st.session_state.update({"ma_papers":[],"ma_step":1})

    if "ma_papers" in st.session_state:
        st.info(f"**{len(st.session_state['ma_papers'])} paper pronti.**")

# ── STEP 2 ─────────────────────────────────────────────────────────────────────
with st.expander("🤖 Step 2 — Estrazione statistiche", expanded=(step==1)):
    outcome = st.text_input("Outcome di interesse",
                            placeholder="es. HbA1c reduction (%), body weight (kg)")

    if st.button("🧠 Estrai con GPT-4o", type="primary",
                 disabled=(not api_key or not outcome or "ma_papers" not in st.session_state)):
        client = OpenAI(api_key=api_key)
        prog   = st.progress(0, "Estrazione...")
        ext, skip = batch_extract(
            st.session_state["ma_papers"], outcome, client,
            progress_callback=lambda i,t: prog.progress(i/t, f"{i}/{t}")
        )
        prog.empty()
        st.session_state.update({"ma_extractable":ext,"ma_skipped":skip,
                                  "ma_outcome":outcome,"ma_step":2})

    # Form manuale
    with st.form("manual"):
        st.caption("Aggiungi studio da full-text")
        c1,c2   = st.columns(2)
        mn = c1.text_input("Nome studio"); mt = c2.selectbox("Tipo",["RCT","cohort","caso-controllo","altro"])
        c3,c4,c5 = st.columns(3)
        mn_total = c3.number_input("n tot",0,100000,0)
        mn_t     = c4.number_input("n tratt.",0,100000,0)
        mn_c     = c5.number_input("n ctrl",0,100000,0)
        c6,c7   = st.columns(2)
        mem = c6.selectbox("Effect measure",["MD","SMD","OR","RR","HR"])
        mes = c7.number_input("Effect size",value=0.0,format="%.4f")
        c8,c9   = st.columns(2)
        mcl = c8.number_input("CI inf",value=0.0,format="%.4f")
        mcu = c9.number_input("CI sup",value=0.0,format="%.4f")
        mout= st.text_input("Outcome")
        if st.form_submit_button("➕ Aggiungi"):
            if "ma_extractable" not in st.session_state:
                st.session_state["ma_extractable"] = []
            st.session_state["ma_extractable"].append({
                "extractable":True,"study_name":mn,"study_type":mt,
                "n_total":mn_total,"n_treatment":mn_t,"n_control":mn_c,
                "effect_measure":mem,"effect_size":mes,"ci_lower":mcl,
                "ci_upper":mcu,"outcome":mout,
            })
            st.success(f"Aggiunto: {mn}")

    if "ma_extractable" in st.session_state:
        ext  = st.session_state["ma_extractable"]
        skip = st.session_state.get("ma_skipped",[])
        st.success(f"✅ {len(ext)} inclusi | ❌ {len(skip)} esclusi")
        for s in ext:
            st.markdown(f"• **{s.get('study_name','?')}** n={s.get('n_total','?')} — "
                        f"{s.get('effect_measure','?')}: {s.get('effect_size','?')} "
                        f"[{s.get('ci_lower','?')}, {s.get('ci_upper','?')}]")

# ── STEP 3 ─────────────────────────────────────────────────────────────────────
with st.expander("📊 Step 3 — Calcolo & Visualizzazioni", expanded=(step==2)):
    if "ma_extractable" not in st.session_state or not st.session_state["ma_extractable"]:
        st.info("Completa Step 2 prima.")
    else:
        eff_label = st.text_input("Etichetta asse X", value=st.session_state.get("ma_outcome","Effect Size"))
        if st.button("⚙️ Esegui meta-analisi", type="primary"):
            prep   = [prepare_study(s) for s in st.session_state["ma_extractable"]]
            result = meta_run(prep, method=method)
            if result.get("error"):
                st.error(result["error"])
            else:
                st.session_state.update({"ma_result":result,
                                          "ma_prepared":[p for p in prep if p],
                                          "ma_egger":egger_test(prep),
                                          "ma_step":3})

        if "ma_result" in st.session_state:
            r = st.session_state["ma_result"]
            m1,m2,m3,m4,m5 = st.columns(5)
            m1.metric("k studi",        r["k"])
            m2.metric("Stima pooled",   f"{r['estimate']:.3f}")
            m3.metric("95% CI",         f"[{r['ci_lower']:.3f}, {r['ci_upper']:.3f}]")
            m4.metric("p",              f"{r['p_value']:.4f}")
            m5.metric("I²",             f"{r['I2']:.1f}%")

            eg = st.session_state.get("ma_egger",{})
            if not eg.get("error"):
                col_bias, = st.columns(1)
                st.caption(f"**Egger:** {eg['bias']} — intercetta={eg['intercept']:.3f}, p={eg['p_value']:.3f}")

            null = 1.0 if r["log_scale"] else 0.0
            st.plotly_chart(forest_plot(st.session_state["ma_prepared"],r,eff_label,null), use_container_width=True)
            st.plotly_chart(funnel_plot(st.session_state["ma_prepared"],r,eff_label,eg), use_container_width=True)

# ── STEP 4 ─────────────────────────────────────────────────────────────────────
with st.expander("📝 Step 4 — Report PRISMA", expanded=(step==3)):
    if "ma_result" not in st.session_state:
        st.info("Completa Step 3 prima.")
    elif not api_key:
        st.warning("Inserisci OpenAI API Key.")
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
            st.download_button("⬇️ Scarica .md", st.session_state["ma_report"],
                               f"meta_{datetime.now():%Y%m%d}_{st.session_state.get('ma_outcome','')[:20]}.md",
                               "text/markdown")
