"""
Research Radar — Dott.ssa Fabrizia Aceto
Dashboard unificata: OpenAlex + Semantic Scholar + Europe PMC + CrossRef + ClinicalTrials
100% API gratuite, nessuna API key richiesta.
"""
import streamlit as st
from datetime import datetime

from aggregator import search_all
from sources.clinical_trials import search_trials, get_recruiting_trials
from sources.openalex import get_trending_concepts, get_citation_trend
from sources.crossref import JOURNALS, get_journal_works

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Research Radar · Fabrizia",
    page_icon="🛰️",
    layout="wide",
)

SOURCE_COLORS = {
    "OpenAlex":         "#2563eb",
    "Semantic Scholar": "#7c3aed",
    "Europe PMC":       "#059669",
    "CrossRef":         "#d97706",
}

st.markdown("""
<style>
.source-badge {
    display:inline-block; padding:2px 10px; border-radius:12px;
    font-size:.75rem; font-weight:600; color:white; margin-right:4px;
}
.oa-badge {
    background:#16a34a; padding:2px 8px; border-radius:12px;
    font-size:.75rem; color:white;
}
.influential {
    background:#fef3c7; color:#92400e;
    padding:2px 8px; border-radius:12px; font-size:.75rem;
}
.paper-row {
    border-bottom:1px solid #e2e8f0; padding:12px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🛰️ Research Radar")
st.caption("Dott.ssa Fabrizia Aceto — OpenAlex · Semantic Scholar · Europe PMC · CrossRef · ClinicalTrials.gov")
st.caption("Tutte le API sono **100% gratuite** — nessuna API key richiesta")
st.markdown("---")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Parametri")

    year_from = st.slider("Da anno", 2015, 2025, 2021)
    max_per   = st.slider("Risultati per fonte", 5, 30, 15)

    st.markdown("---")
    st.subheader("🔌 Fonti attive")
    use_oa   = st.checkbox("OpenAlex",         value=True)
    use_ss   = st.checkbox("Semantic Scholar", value=True)
    use_epmc = st.checkbox("Europe PMC",       value=True)
    use_cr   = st.checkbox("CrossRef",         value=True)
    use_ct   = st.checkbox("ClinicalTrials",   value=True)

    selected_sources = []
    if use_oa:   selected_sources.append("openalex")
    if use_ss:   selected_sources.append("semantic_scholar")
    if use_epmc: selected_sources.append("europe_pmc")
    if use_cr:   selected_sources.append("crossref")

    st.markdown("---")
    st.subheader("⚡ Query rapide")
    quick = [
        "GLP-1 receptor agonist type 2 diabetes",
        "SGLT2 inhibitor cardiovascular outcome",
        "continuous glucose monitoring HbA1c",
        "insulin resistance PCOS treatment",
        "CGM time in range outcomes",
        "semaglutide obesity treatment",
        "thyroid nodule ultrasound management",
        "diabetic kidney disease SGLT2",
        "endocrinology reproductive medicine",
        "metformin diabetes prevention",
    ]
    for q in quick:
        if st.button(q, use_container_width=True, key=f"q_{q[:20]}"):
            st.session_state["quick_q"] = q

# ── Main tabs ──────────────────────────────────────────────────────────────────
tab_search, tab_trials, tab_trends, tab_journals = st.tabs([
    "🔍 Ricerca Multi-fonte",
    "🏥 Trial Clinici",
    "📈 Trend & Concetti",
    "📰 Journal Watch",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RICERCA MULTI-FONTE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_search:
    default_q = st.session_state.pop("quick_q", "")
    query = st.text_input(
        "Query di ricerca",
        value=default_q,
        placeholder="es. GLP-1 diabetes HbA1c randomized controlled trial",
    )

    col_btn, col_oa_only = st.columns([1, 2])
    with col_btn:
        search_btn = st.button("🚀 Cerca su tutte le fonti", type="primary", use_container_width=True)
    with col_oa_only:
        oa_only = st.checkbox("Solo Open Access", value=False)

    if search_btn and query.strip():
        with st.spinner(f"Interrogazione parallela di {len(selected_sources)} database..."):
            results = search_all(
                query,
                max_per_source=max_per,
                year_from=year_from,
                sources=selected_sources if selected_sources else None,
            )
        st.session_state["results"] = results
        st.session_state["last_query"] = query

    if "results" in st.session_state:
        results = st.session_state["results"]
        stats   = results["stats"]
        merged  = results["merged"]

        # Metriche riassuntive
        cols = st.columns(len(selected_sources) + 1)
        cols[0].metric("📚 Totale unici", stats["total_unique"])
        source_display = {
            "openalex": "OpenAlex",
            "semantic_scholar": "Semantic Scholar",
            "europe_pmc": "Europe PMC",
            "crossref": "CrossRef",
        }
        for i, src in enumerate(selected_sources):
            label = source_display.get(src, src)
            count = stats["by_source"].get(src, 0)
            err   = stats.get("errors", {}).get(src, "")
            cols[i + 1].metric(label, count, delta="⚠️ errore" if err else None)

        if stats.get("errors"):
            for src, err in stats["errors"].items():
                st.warning(f"⚠️ {src}: {err}")

        # Filtro open access
        display_papers = [p for p in merged if p.get("open_access")] if oa_only else merged

        st.markdown(f"### {len(display_papers)} paper {'open access' if oa_only else 'totali'}")

        # Visualizzazione paper
        for i, paper in enumerate(display_papers):
            src_color = SOURCE_COLORS.get(paper.get("source", ""), "#64748b")
            oa_html = '<span class="oa-badge">🔓 Open Access</span>' if paper.get("open_access") else ""
            infl    = paper.get("influential", 0)
            infl_html = f'<span class="influential">⭐ {infl} influential</span>' if infl else ""

            with st.expander(
                f"[{i+1}] {paper.get('title','')[:100]}{'...' if len(paper.get('title',''))>100 else ''}"
                f"  — {paper.get('year','')}  |  {paper.get('citations',0):,} citazioni"
            ):
                st.markdown(
                    f'<span class="source-badge" style="background:{src_color}">'
                    f'{paper.get("source","")}</span> {oa_html} {infl_html}',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns([3, 1])
                with c1:
                    if paper.get("authors"):
                        st.caption(f"**Autori:** {paper['authors']}")
                    if paper.get("journal"):
                        st.caption(f"**Rivista:** {paper['journal']}")
                with c2:
                    if paper.get("url"):
                        st.markdown(f"[**→ Apri paper**]({paper['url']})")
                    if paper.get("pubmed_url"):
                        st.markdown(f"[→ PubMed]({paper['pubmed_url']})")

                # TLDR da Semantic Scholar (già AI-generated)
                if paper.get("tldr"):
                    st.info(f"**AI Summary (S2):** {paper['tldr']}")

                # Abstract
                abstract = paper.get("abstract", "")
                if abstract:
                    st.markdown("**Abstract:**")
                    st.markdown(abstract[:800] + ("..." if len(abstract) > 800 else ""))

                # Concetti/tag
                tags = paper.get("concepts") or paper.get("subjects") or paper.get("fields") or []
                if tags:
                    st.caption("Tags: " + " · ".join(str(t) for t in tags[:6]))

        # Download CSV
        if display_papers:
            import csv, io
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=[
                "source","title","year","authors","journal","citations","doi","url","open_access"
            ])
            writer.writeheader()
            for p in display_papers:
                writer.writerow({k: p.get(k, "") for k in writer.fieldnames})
            st.download_button(
                "⬇️ Esporta CSV",
                data=buf.getvalue(),
                file_name=f"research_{datetime.now().strftime('%Y%m%d')}_{st.session_state.get('last_query','')[:20]}.csv",
                mime="text/csv",
            )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — TRIAL CLINICI
# ═══════════════════════════════════════════════════════════════════════════════
with tab_trials:
    st.subheader("🏥 ClinicalTrials.gov — Trial in Diabetologia & Endocrinologia")

    col_cond, col_intr = st.columns(2)
    condition    = col_cond.text_input("Condizione", value="type 2 diabetes", placeholder="es. type 2 diabetes")
    intervention = col_intr.text_input("Intervento (opz.)", placeholder="es. semaglutide")

    col_status, col_max = st.columns(2)
    status_opts = col_status.multiselect(
        "Stato trial",
        ["RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED", "NOT_YET_RECRUITING"],
        default=["RECRUITING", "NOT_YET_RECRUITING"],
        format_func=lambda x: {
            "RECRUITING":            "🟢 In reclutamento",
            "ACTIVE_NOT_RECRUITING": "🟡 Attivo",
            "COMPLETED":             "🔵 Completato",
            "NOT_YET_RECRUITING":    "⚪ Non ancora avviato",
        }.get(x, x),
    )
    max_trials = col_max.slider("Max trial", 5, 50, 20, key="ct_max")

    if st.button("🔍 Cerca Trial", type="primary"):
        with st.spinner("Ricerca su ClinicalTrials.gov..."):
            try:
                trials = search_trials(
                    condition=condition,
                    intervention=intervention,
                    status=status_opts or None,
                    max_results=max_trials,
                )
                st.session_state["trials"] = trials
            except Exception as e:
                st.error(f"Errore ClinicalTrials: {e}")

    if "trials" in st.session_state:
        trials = st.session_state["trials"]
        st.success(f"**{len(trials)} trial trovati**")

        status_icon = {
            "In reclutamento": "🟢",
            "Non ancora avviato": "⚪",
            "Attivo (no reclutamento)": "🟡",
            "Completato": "🔵",
            "Terminato": "🔴",
        }

        for t in trials:
            icon = status_icon.get(t.get("status", ""), "❓")
            with st.expander(
                f"{icon} {t.get('title','')[:90]}{'...' if len(t.get('title',''))>90 else ''}"
                f"  |  {t.get('phase','N/D')}  |  {t.get('enrollment',0):,} pz"
            ):
                c1, c2, c3 = st.columns(3)
                c1.metric("Stato", t.get("status", "N/D"))
                c2.metric("Fase",  t.get("phase", "N/D"))
                c3.metric("Pazienti", f"{t.get('enrollment', 0):,}")

                if t.get("start_date"):
                    st.caption(f"Avvio: {t['start_date']} | Completamento: {t.get('completion','N/D')}")
                if t.get("interventions"):
                    st.markdown(f"**Interventi:** {t['interventions']}")
                if t.get("sponsor"):
                    st.caption(f"Sponsor: {t['sponsor']}")
                if t.get("countries"):
                    st.caption(f"Paesi: {t['countries']}")
                if t.get("summary"):
                    st.markdown(f"**Sommario:** {t['summary'][:400]}...")
                st.markdown(f"[**→ Apri su ClinicalTrials.gov**]({t.get('url','')})")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TREND & CONCETTI
# ═══════════════════════════════════════════════════════════════════════════════
with tab_trends:
    st.subheader("📈 Trend della Ricerca — OpenAlex")

    trend_query = st.text_input(
        "Query per analisi trend",
        value="diabetes",
        placeholder="es. diabetes, GLP-1, CGM, thyroid",
        key="trend_q",
    )

    if st.button("📊 Analizza Trend", type="primary"):
        with st.spinner("Analisi trend su OpenAlex..."):
            try:
                concepts = get_trending_concepts(trend_query, top_n=12)
                trend    = get_citation_trend(trend_query)
                st.session_state["concepts"] = concepts
                st.session_state["trend"]    = trend
                st.session_state["trend_q_label"] = trend_query
            except Exception as e:
                st.error(f"Errore OpenAlex: {e}")

    if "trend" in st.session_state:
        q_label = st.session_state.get("trend_q_label", "")
        st.markdown(f"#### Pubblicazioni per anno: _{q_label}_")
        st.bar_chart(st.session_state["trend"])

        st.markdown(f"#### Concetti più associati a _{q_label}_")
        concepts = st.session_state["concepts"]
        if concepts:
            concept_data = {c["concept"]: c["count"] for c in concepts}
            st.bar_chart(concept_data)

            st.markdown("**Top concetti:**")
            for c in concepts[:8]:
                st.markdown(f"• **{c['concept']}** — {c['count']} paper")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — JOURNAL WATCH
# ═══════════════════════════════════════════════════════════════════════════════
with tab_journals:
    st.subheader("📰 Journal Watch — Ultime pubblicazioni dalle riviste chiave")

    selected_journal = st.selectbox(
        "Rivista",
        list(JOURNALS.keys()),
        index=0,
    )

    n_articles = st.slider("Ultimi N articoli", 5, 25, 10, key="jw_n")

    if st.button("📰 Carica ultimi articoli", type="primary"):
        issn = JOURNALS[selected_journal]
        with st.spinner(f"Caricamento da {selected_journal}..."):
            try:
                articles = get_journal_works(issn, max_results=n_articles)
                st.session_state["journal_articles"] = articles
                st.session_state["journal_name"] = selected_journal
            except Exception as e:
                st.error(f"Errore CrossRef: {e}")

    if "journal_articles" in st.session_state:
        jname = st.session_state.get("journal_name", "")
        articles = st.session_state["journal_articles"]
        st.markdown(f"**{len(articles)} articoli recenti — {jname}**")
        for a in articles:
            st.markdown(
                f"• [{a.get('title','N/D')[:100]}]({a.get('url','#')}) "
                f"— {a.get('citations', 0):,} citazioni"
            )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "**Fonti:** OpenAlex (CC0) · Semantic Scholar (AI2) · Europe PMC (EMBL-EBI) · "
    "CrossRef · ClinicalTrials.gov (NIH) — tutte gratuite e senza API key. "
    "*Strumento di supporto alla ricerca — non sostituisce la valutazione clinica.*"
)
