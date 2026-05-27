import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deliverables', 'pubmed-researcher'))

import streamlit as st
from openai import OpenAI
from pubmed_fetcher import search_pubmed, fetch_papers
from ai_analyzer import analyze_paper, synthesize_research

st.title("🔬 PubMed AI")
st.caption("NCBI PubMed (gratuito) + analisi GPT-4o per ogni paper")

with st.sidebar:
    api_key    = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY",""), type="password")
    max_r      = st.slider("Num. articoli", 5, 40, 15)
    year_f     = st.number_input("Da anno", 2000, 2026, 2020)
    ai_mode    = st.radio("Analisi AI", ["Tutto","Solo sintesi","Nessuna"],
                          format_func=lambda x: {"Tutto":"🧠 Paper + Sintesi","Solo sintesi":"📋 Solo sintesi","Nessuna":"❌ Nessuna"}[x])
    st.markdown("---")
    st.caption("**Query rapide**")
    for q in ["GLP-1 agonists HbA1c type 2 diabetes","continuous glucose monitoring outcomes",
              "SGLT2 inhibitors cardiovascular","insulin resistance PCOS",
              "thyroid nodule ultrasound","semaglutide weight loss"]:
        if st.button(q, use_container_width=True, key=f"pq_{q[:15]}"):
            st.session_state["pq"] = q

query = st.text_input("Query PubMed", value=st.session_state.pop("pq",""),
                      placeholder="es. GLP-1 HbA1c randomized controlled trial")

if st.button("🔍 Cerca", type="primary") and query.strip():
    if not api_key and ai_mode != "Nessuna":
        st.warning("Inserisci OpenAI API Key nella sidebar per l'analisi AI.")
    with st.spinner("Ricerca PubMed..."):
        try:
            pmids  = search_pubmed(query, max_results=max_r,
                                   date_range=(f"{year_f}/01/01","2099/12/31"))
            papers = fetch_papers(pmids)
        except Exception as e:
            st.error(str(e)); st.stop()
    st.session_state["pm_papers"] = papers
    st.session_state["pm_q"]      = query
    st.session_state["pm_analyses"] = []

    if api_key and ai_mode in ("Tutto",):
        client   = OpenAI(api_key=api_key)
        analyses = []
        prog     = st.progress(0, "Analisi AI...")
        for i, p in enumerate(papers):
            try:    analyses.append(analyze_paper(p, client))
            except: analyses.append({})
            prog.progress((i+1)/len(papers))
        prog.empty()
        st.session_state["pm_analyses"] = analyses

    st.success(f"{len(papers)} articoli trovati per: _{query}_")

if "pm_papers" in st.session_state:
    papers   = st.session_state["pm_papers"]
    analyses = st.session_state.get("pm_analyses", [{} for _ in papers])

    tab_p, tab_s = st.tabs([f"📄 Articoli ({len(papers)})", "📊 Sintesi letteratura"])

    with tab_p:
        for i, (p, a) in enumerate(zip(papers, analyses)):
            ev_color = {"alto":"#dcfce7","medio":"#fef9c3","basso":"#fee2e2"}.get(
                (a.get("evidence_level") or "").lower(), "#f1f5f9")
            with st.expander(f"[{i+1}] {p['title'][:95]}  — {p.get('year','')}"):
                c1, c2 = st.columns([3,1])
                with c1:
                    if p.get("authors"): st.caption(f"**Autori:** {p['authors']}")
                    if p.get("journal"): st.caption(f"**Rivista:** {p['journal']}")
                with c2:
                    if a.get("evidence_level"):
                        st.markdown(f"<span style='background:{ev_color};padding:3px 8px;border-radius:10px;font-size:.8rem'>{a['evidence_level'].upper()}</span>", unsafe_allow_html=True)
                    if a.get("study_type"): st.caption(a["study_type"])
                if p.get("url"): st.markdown(f"[→ PubMed]({p['url']})")
                if a.get("summary"):
                    st.info(a["summary"])
                    col_l, col_r = st.columns(2)
                    with col_l:
                        for f in a.get("key_findings",[]): st.markdown(f"• {f}")
                    with col_r:
                        for im in a.get("clinical_implications",[]): st.markdown(f"→ {im}")
                elif p.get("abstract"):
                    st.markdown(p["abstract"][:500] + "...")

    with tab_s:
        if api_key and st.button("🧠 Genera sintesi letteratura", type="primary"):
            client = OpenAI(api_key=api_key)
            ana    = analyses if analyses and any(a.get("summary") for a in analyses) else []
            if not ana:
                with st.spinner("Analisi rapida per sintesi..."):
                    ana = []
                    for p in papers[:10]:
                        try:    ana.append(analyze_paper(p, client))
                        except: ana.append({})
            with st.spinner("Generazione sintesi..."):
                synth = synthesize_research(papers, ana, st.session_state["pm_q"], client)
            st.markdown(synth)
            st.download_button("⬇️ Scarica sintesi", synth,
                               f"sintesi_{st.session_state['pm_q'][:20]}.md", "text/markdown")
        elif not api_key:
            st.info("Inserisci OpenAI API Key per la sintesi.")
