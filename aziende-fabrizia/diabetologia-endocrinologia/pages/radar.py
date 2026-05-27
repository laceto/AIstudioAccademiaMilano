import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deliverables', 'research-radar'))

import streamlit as st
from aggregator import search_all
from sources.clinical_trials import search_trials
from sources.openalex import get_trending_concepts, get_citation_trend
from sources.crossref import JOURNALS, get_journal_works

SOURCE_COLORS = {
    "OpenAlex": "#2563eb", "Semantic Scholar": "#7c3aed",
    "Europe PMC": "#059669", "CrossRef": "#d97706",
}

st.title("🛰️ Research Radar")
st.caption("OpenAlex · Semantic Scholar · Europe PMC · CrossRef · ClinicalTrials — **zero API key**")

with st.sidebar:
    year_from = st.slider("Da anno", 2015, 2025, 2021)
    max_per   = st.slider("Risultati per fonte", 5, 30, 15)
    use_oa    = st.checkbox("OpenAlex",          value=True)
    use_ss    = st.checkbox("Semantic Scholar",  value=True)
    use_epmc  = st.checkbox("Europe PMC",        value=True)
    use_cr    = st.checkbox("CrossRef",          value=True)
    selected  = [s for s, ok in [("openalex", use_oa), ("semantic_scholar", use_ss),
                                  ("europe_pmc", use_epmc), ("crossref", use_cr)] if ok]
    st.markdown("---")
    st.caption("**Query rapide**")
    for q in ["GLP-1 diabetes HbA1c", "SGLT2 cardiovascular outcome",
              "CGM time in range", "semaglutide obesity", "thyroid nodule management",
              "insulin resistance PCOS", "diabetic kidney disease"]:
        if st.button(q, use_container_width=True, key=q):
            st.session_state["rq"] = q

tab_search, tab_trials, tab_trends = st.tabs(["🔍 Ricerca", "🏥 Trial Clinici", "📈 Trend"])

with tab_search:
    query = st.text_input("Query", value=st.session_state.pop("rq", ""),
                          placeholder="es. GLP-1 type 2 diabetes randomized")
    if st.button("🚀 Cerca su tutte le fonti", type="primary") and query.strip():
        with st.spinner("Interrogazione parallela in corso..."):
            st.session_state["r_res"] = search_all(query, max_per, year_from, selected)
            st.session_state["r_q"]   = query

    if "r_res" in st.session_state:
        res    = st.session_state["r_res"]
        merged = res["merged"]
        stats  = res["stats"]
        cols   = st.columns(len(selected) + 1)
        cols[0].metric("Totale unici", stats["total_unique"])
        for i, src in enumerate(selected):
            cols[i+1].metric(src.replace("_", " ").title(), stats["by_source"].get(src, 0))

        oa_filter = st.checkbox("Solo Open Access")
        papers = [p for p in merged if p.get("open_access")] if oa_filter else merged
        st.markdown(f"**{len(papers)} paper**")

        for i, p in enumerate(papers):
            color = SOURCE_COLORS.get(p.get("source", ""), "#64748b")
            oa    = "🔓 " if p.get("open_access") else ""
            with st.expander(f"[{i+1}] {oa}{p.get('title','')[:90]}  — {p.get('year','')} | {p.get('citations',0):,} cit."):
                st.markdown(f"<span style='background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:.75rem'>{p.get('source','')}</span>", unsafe_allow_html=True)
                if p.get("authors"): st.caption(f"**Autori:** {p['authors']}")
                if p.get("journal"): st.caption(f"**Rivista:** {p['journal']}")
                if p.get("tldr"):    st.info(f"**AI Summary:** {p['tldr']}")
                if p.get("abstract"):st.markdown(p["abstract"][:600] + "...")
                if p.get("url"):     st.markdown(f"[→ Apri paper]({p['url']})")

        import csv, io
        if papers:
            buf = io.StringIO()
            w   = csv.DictWriter(buf, fieldnames=["source","title","year","authors","journal","citations","doi","url"])
            w.writeheader()
            [w.writerow({k: p.get(k,"") for k in w.fieldnames}) for p in papers]
            st.download_button("⬇️ CSV", buf.getvalue(), f"radar_{st.session_state.get('r_q','')[:20]}.csv", "text/csv")

with tab_trials:
    col1, col2 = st.columns(2)
    cond = col1.text_input("Condizione", "type 2 diabetes")
    intr = col2.text_input("Intervento (opz.)", "")
    stati = st.multiselect("Stato", ["RECRUITING","ACTIVE_NOT_RECRUITING","COMPLETED"],
                           default=["RECRUITING"],
                           format_func=lambda x: {"RECRUITING":"🟢 Reclutamento",
                                                   "ACTIVE_NOT_RECRUITING":"🟡 Attivo",
                                                   "COMPLETED":"🔵 Completato"}.get(x,x))
    if st.button("🔍 Cerca Trial", type="primary"):
        with st.spinner("ClinicalTrials.gov..."):
            try:
                st.session_state["trials"] = search_trials(cond, intr, stati or None, 20)
            except Exception as e:
                st.error(str(e))
    if "trials" in st.session_state:
        for t in st.session_state["trials"]:
            with st.expander(f"{t.get('status','')} | {t.get('title','')[:80]} | {t.get('phase','')}"):
                c1,c2,c3 = st.columns(3)
                c1.metric("Stato",    t.get("status",""))
                c2.metric("Fase",     t.get("phase",""))
                c3.metric("Pazienti", t.get("enrollment",0))
                if t.get("interventions"): st.markdown(f"**Interventi:** {t['interventions']}")
                if t.get("sponsor"):       st.caption(f"Sponsor: {t['sponsor']}")
                if t.get("summary"):       st.markdown(t["summary"][:400])
                st.markdown(f"[→ ClinicalTrials.gov]({t.get('url','')})")

with tab_trends:
    tq = st.text_input("Query trend", "diabetes", key="tq")
    if st.button("📊 Analizza", type="primary"):
        with st.spinner("OpenAlex..."):
            try:
                st.session_state["trend"]    = get_citation_trend(tq)
                st.session_state["concepts"] = get_trending_concepts(tq, 12)
            except Exception as e:
                st.error(str(e))
    if "trend" in st.session_state:
        st.bar_chart(st.session_state["trend"])
        if "concepts" in st.session_state:
            st.bar_chart({c["concept"]: c["count"] for c in st.session_state["concepts"]})
