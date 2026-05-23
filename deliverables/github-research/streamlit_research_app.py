import os
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "github_research"))

st.set_page_config(page_title="GitHub AI Research", page_icon="🔬", layout="wide")

TIER_COLOURS = {"S": "#22c55e", "A": "#3b82f6", "B": "#f59e0b", "C": "#6b7280"}


def tier_badge(tier: str) -> str:
    colour = TIER_COLOURS.get(tier, "#6b7280")
    return f'<span style="background:{colour};color:white;padding:2px 8px;border-radius:4px;font-weight:bold;">{tier}</span>'


st.title("GitHub AI Research Dashboard")
st.caption("Scout -> Analyst -> Curator -> Reporter")

with st.sidebar:
    st.header("Settings")
    token = st.text_input("GitHub Token (optional)", type="password",
                          help="Raises rate limit from 60 to 5000 req/h")
    from search_repos import AI_TOPICS
    selected_topics = st.multiselect("Topics", AI_TOPICS, default=AI_TOPICS[:5])
    min_stars = st.slider("Min stars", 50, 5000, 200, step=50)
    max_per_topic = st.slider("Max repos per topic", 5, 30, 10)
    run = st.button("Run Research", type="primary")

if run and selected_topics:
    from search_repos import search_all_topics
    from evaluate_repo import rank_repos
    from report import deduplicate, generate_report

    with st.spinner("Scout scanning GitHub..."):
        raw = search_all_topics(
            topics=selected_topics,
            min_stars=min_stars,
            max_per_topic=max_per_topic,
            token=token or None,
        )

    with st.spinner("Analyst scoring..."):
        ranked = {t: rank_repos(repos) for t, repos in raw.items()}

    with st.spinner("Curator organising..."):
        categorised = deduplicate(ranked)

    all_scored = [rs for v in categorised.values() for rs in v]
    all_scored.sort(key=lambda x: x.score, reverse=True)

    st.success(f"Found {len(all_scored)} unique repos across {len(categorised)} categories")

    rows = [
        {
            "Tier": rs.tier,
            "Repo": rs.repo.full_name,
            "Stars": rs.repo.stars,
            "Language": rs.repo.language,
            "Score": rs.score,
            "URL": rs.repo.url,
            "Description": rs.repo.description[:80],
        }
        for rs in all_scored
    ]
    df = pd.DataFrame(rows)

    st.subheader("Top Repos")
    col1, col2, col3, col4 = st.columns(4)
    for label, tier in [("S Tier", "S"), ("A Tier", "A"), ("B Tier", "B"), ("C Tier", "C")]:
        count = len(df[df["Tier"] == tier])
        col1.metric(label, count) if tier == "S" else \
        col2.metric(label, count) if tier == "A" else \
        col3.metric(label, count) if tier == "B" else \
        col4.metric(label, count)

    top10 = df.head(10).copy()
    st.markdown(
        top10.to_html(
            escape=False, index=False,
            formatters={"Tier": tier_badge, "Repo": lambda r: f'<a href="{df.loc[df["Repo"]==r, "URL"].values[0]}" target="_blank">{r}</a>'}
        ),
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.histogram(df, x="Stars", nbins=20, title="Stars Distribution", log_x=True)
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        lang_counts = df["Language"].value_counts().head(8).reset_index()
        lang_counts.columns = ["Language", "Count"]
        fig2 = px.pie(lang_counts, names="Language", values="Count", title="Languages")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("All Results")
    tier_filter = st.multiselect("Filter by tier", ["S", "A", "B", "C"], default=["S", "A", "B", "C"])
    filtered = df[df["Tier"].isin(tier_filter)]
    st.dataframe(filtered.drop(columns=["URL"]), use_container_width=True)

    report_md = generate_report(categorised)
    st.download_button(
        "Download Markdown Report",
        data=report_md,
        file_name=f"github_ai_research_{pd.Timestamp.now().date()}.md",
        mime="text/markdown",
    )
else:
    st.info("Configure settings in the sidebar and click **Run Research** to start.")
    st.markdown("""
    ### How it works

    | Agent | What it does |
    |-------|--------------|
    | **Scout** | Queries GitHub Search API for repos by topic |
    | **Analyst** | Scores each repo: stars, activity, growth, community |
    | **Curator** | Deduplicates and organises into 5 AI categories |
    | **Reporter** | Renders this dashboard + downloadable markdown digest |

    ### Quick start (CLI)
    ```bash
    pip install -r requirements-research.txt
    export GITHUB_TOKEN=ghp_...
    python scripts/github_research/main.py --topics llm rag ai-agents
    ```
    """)
