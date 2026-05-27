"""
PubMed Researcher — Dott.ssa Fabrizia Aceto
Diabetologia & Endocrinologia

Streamlit app: ricerca PubMed + analisi AI per ogni paper + sintesi della letteratura.
"""
import os
import streamlit as st
from openai import OpenAI

from pubmed_fetcher import search_pubmed, fetch_papers
from ai_analyzer import analyze_paper, synthesize_research, generate_clinical_question

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PubMed Researcher · Dott.ssa Fabrizia",
    page_icon="🔬",
    layout="wide",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.paper-card {
    background: #f8fafc;
    border-left: 4px solid #2563eb;
    padding: 1rem 1.2rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 1rem;
}
.badge-high   { background:#dcfce7; color:#166534; padding:2px 8px; border-radius:12px; font-size:.8rem; }
.badge-medium { background:#fef9c3; color:#713f12; padding:2px 8px; border-radius:12px; font-size:.8rem; }
.badge-low    { background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; font-size:.8rem; }
.badge-nd     { background:#f1f5f9; color:#475569; padding:2px 8px; border-radius:12px; font-size:.8rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🔬 PubMed Researcher")
st.caption("Dott.ssa Fabrizia Aceto — Diabetologia & Endocrinologia")
st.markdown("---")

# ── Sidebar: configurazione ────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurazione")

    api_key = st.text_input(
        "OpenAI API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="Necessaria per l'analisi AI dei paper",
    )

    st.markdown("---")
    st.subheader("🔎 Parametri ricerca")

    max_results = st.slider("Numero massimo di articoli", 5, 50, 15)

    sort_by = st.selectbox(
        "Ordina per",
        ["relevance", "pub_date"],
        format_func=lambda x: "Rilevanza" if x == "relevance" else "Data pubblicazione",
    )

    use_date_filter = st.checkbox("Filtra per data", value=False)
    date_range = None
    if use_date_filter:
        col1, col2 = st.columns(2)
        y_from = col1.number_input("Da (anno)", 2000, 2026, 2020)
        y_to = col2.number_input("A (anno)", 2000, 2026, 2026)
        date_range = (f"{y_from}/01/01", f"{y_to}/12/31")

    st.markdown("---")
    st.subheader("🤖 Livello analisi AI")
    ai_mode = st.radio(
        "Modalità",
        ["paper_singolo", "sintesi_completa", "tutto"],
        format_func=lambda x: {
            "paper_singolo": "Analisi per paper",
            "sintesi_completa": "Solo sintesi finale",
            "tutto": "Analisi + Sintesi + Domande",
        }[x],
        index=2,
    )

    st.markdown("---")
    st.caption("💡 Query rapide per Fabrizia")
    quick_queries = [
        "GLP-1 agonists HbA1c reduction type 2 diabetes",
        "continuous glucose monitoring outcomes",
        "SGLT2 inhibitors cardiovascular benefit",
        "insulin resistance PCOS treatment",
        "diabetic neuropathy new treatments 2024",
        "thyroid nodule management guidelines",
        "metformin type 2 diabetes first line",
        "CGM time in range clinical outcomes",
    ]
    for q in quick_queries:
        if st.button(q, use_container_width=True):
            st.session_state["quick_query"] = q

# ── Main: input ricerca ────────────────────────────────────────────────────────
default_q = st.session_state.pop("quick_query", "")
query = st.text_input(
    "Query di ricerca PubMed",
    value=default_q,
    placeholder="es. GLP-1 receptor agonists type 2 diabetes HbA1c",
)

col_search, col_tip = st.columns([1, 3])
with col_search:
    search_btn = st.button("🔍 Cerca su PubMed", type="primary", use_container_width=True)
with col_tip:
    st.caption("Puoi usare operatori booleani: AND, OR, NOT. Es: (metformin OR GLP-1) AND (HbA1c) AND (randomized)")

# ── Ricerca ────────────────────────────────────────────────────────────────────
if search_btn and query.strip():
    if not api_key and ai_mode != "nessuna":
        st.warning("Inserisci una OpenAI API Key nella sidebar per l'analisi AI.")

    with st.spinner("Ricerca su PubMed in corso..."):
        try:
            pmids = search_pubmed(query, max_results=max_results, date_range=date_range, sort=sort_by)
        except Exception as e:
            st.error(f"Errore ricerca PubMed: {e}")
            st.stop()

    if not pmids:
        st.warning("Nessun articolo trovato. Prova a modificare la query.")
        st.stop()

    st.success(f"**{len(pmids)} articoli trovati** su PubMed per: _{query}_")

    with st.spinner(f"Download dati per {len(pmids)} articoli..."):
        try:
            papers = fetch_papers(pmids)
        except Exception as e:
            st.error(f"Errore download paper: {e}")
            st.stop()

    # ── Analisi AI ─────────────────────────────────────────────────────────────
    analyses = []
    if api_key and ai_mode in ("paper_singolo", "tutto"):
        client = OpenAI(api_key=api_key)
        progress = st.progress(0, text="Analisi AI paper in corso...")
        for i, paper in enumerate(papers):
            try:
                analysis = analyze_paper(paper, client)
            except Exception as e:
                analysis = {"summary": f"Errore AI: {e}", "key_findings": []}
            analyses.append(analysis)
            progress.progress((i + 1) / len(papers), text=f"Analisi paper {i+1}/{len(papers)}")
        progress.empty()
    else:
        analyses = [{} for _ in papers]

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab_papers, tab_synthesis, tab_questions = st.tabs([
        f"📄 Articoli ({len(papers)})",
        "📊 Sintesi della letteratura",
        "❓ Domande cliniche aperte",
    ])

    # Tab 1 — Lista paper con analisi
    with tab_papers:
        for i, (paper, analysis) in enumerate(zip(papers, analyses)):
            ev = analysis.get("evidence_level", "").lower()
            badge_class = {"alto": "badge-high", "medio": "badge-medium", "basso": "badge-low"}.get(ev, "badge-nd")
            badge_label = analysis.get("evidence_level", "N/D").upper()
            study_type = analysis.get("study_type", "")

            with st.expander(
                f"[{i+1}] {paper['title'][:100]}{'...' if len(paper['title']) > 100 else ''}  "
                f"— {paper.get('year', '')}",
                expanded=(i == 0),
            ):
                col_meta, col_ev = st.columns([3, 1])
                with col_meta:
                    st.markdown(f"**Autori:** {paper.get('authors', 'N/D')}")
                    st.markdown(f"**Rivista:** {paper.get('journal', 'N/D')}")
                    if paper.get("doi"):
                        st.markdown(f"**DOI:** `{paper['doi']}`")
                    st.markdown(f"**[Apri su PubMed →]({paper['url']})**")
                with col_ev:
                    st.markdown(
                        f"<span class='{badge_class}'>{badge_label}</span>",
                        unsafe_allow_html=True,
                    )
                    if study_type:
                        st.caption(study_type)

                if paper.get("mesh"):
                    st.caption("MeSH: " + " · ".join(paper["mesh"]))

                st.markdown("---")

                if analysis and analysis.get("summary"):
                    st.markdown("**🤖 Sintesi AI**")
                    st.info(analysis["summary"])

                    c1, c2 = st.columns(2)
                    with c1:
                        if analysis.get("key_findings"):
                            st.markdown("**Principali findings**")
                            for f in analysis["key_findings"]:
                                st.markdown(f"• {f}")
                    with c2:
                        if analysis.get("clinical_implications"):
                            st.markdown("**Implicazioni cliniche**")
                            for impl in analysis["clinical_implications"]:
                                st.markdown(f"→ {impl}")

                    if analysis.get("population"):
                        st.caption(f"Popolazione: {analysis['population']}")
                    if analysis.get("primary_outcome"):
                        st.caption(f"Outcome primario: {analysis['primary_outcome']}")

                elif paper.get("abstract"):
                    with st.container():
                        st.markdown("**Abstract**")
                        st.markdown(paper["abstract"])

    # Tab 2 — Sintesi complessiva
    with tab_synthesis:
        if api_key and ai_mode in ("sintesi_completa", "tutto"):
            if ai_mode == "sintesi_completa":
                client_s = OpenAI(api_key=api_key)
                with st.spinner("Generazione sintesi complessiva..."):
                    raw_analyses = []
                    for paper in papers:
                        try:
                            raw_analyses.append(analyze_paper(paper, client_s))
                        except Exception:
                            raw_analyses.append({})
                synthesis = synthesize_research(papers, raw_analyses, query, client_s)
            else:
                client_s = OpenAI(api_key=api_key)
                with st.spinner("Generazione sintesi complessiva..."):
                    synthesis = synthesize_research(papers, analyses, query, client_s)

            st.markdown(synthesis)
        elif not api_key:
            st.info("Inserisci una API Key nella sidebar per generare la sintesi.")
        else:
            st.info("Seleziona 'Sintesi completa' o 'Tutto' nella sidebar per questa tab.")

        st.markdown("---")
        st.subheader("📈 Distribuzione temporale")
        years = [p.get("year", "N/D") for p in papers if p.get("year")]
        if years:
            from collections import Counter
            year_counts = Counter(years)
            year_data = dict(sorted(year_counts.items()))
            st.bar_chart(year_data)

        if analyses and any(a.get("evidence_level") for a in analyses):
            st.subheader("🎯 Distribuzione livello di evidenza")
            from collections import Counter
            ev_counts = Counter(
                a.get("evidence_level", "N/D") for a in analyses if a.get("evidence_level")
            )
            st.bar_chart(dict(ev_counts))

    # Tab 3 — Domande cliniche
    with tab_questions:
        if api_key and ai_mode == "tutto":
            client_q = OpenAI(api_key=api_key)
            with st.spinner("Generazione domande cliniche..."):
                try:
                    questions = generate_clinical_question(papers, analyses, client_q)
                    st.markdown(questions)
                except Exception as e:
                    st.error(f"Errore generazione domande: {e}")
        elif not api_key:
            st.info("Inserisci una API Key per generare domande cliniche.")
        else:
            st.info("Seleziona la modalità 'Tutto' nella sidebar per questa funzione.")

elif search_btn and not query.strip():
    st.warning("Inserisci una query di ricerca.")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Dati da **PubMed / NCBI E-utilities** (NIH) — "
    "Analisi AI da **OpenAI GPT-4o** — "
    "*Strumento di supporto alla ricerca — non sostituisce la valutazione clinica.*"
)
