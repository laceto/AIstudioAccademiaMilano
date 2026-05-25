"""
AI Studio Accademia Milano — LangGraph Pipeline Streamlit UI.
Run: streamlit run app.py
Requires ANTHROPIC_API_KEY in environment or .streamlit/secrets.toml.
"""
import os
import sys

import streamlit as st

# Allow running from the deliverable folder directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state import PRICING_TABLE

st.set_page_config(
    page_title="AI Studio — LangGraph",
    page_icon="🤖",
    layout="wide",
)

# ── Page header ───────────────────────────────────────────────────────────────
st.title("🤖 AI Studio Accademia Milano")
st.caption("6-Agent LangGraph Pipeline — Stacy · Gianni · Chiara · Risk Panel · Marco · Francesca")

# ── Sidebar: architecture + pricing ──────────────────────────────────────────
with st.sidebar:
    st.header("Pipeline Architecture")
    st.code(
        "START\n"
        "  └─► [Stacy] classify\n"
        "        ├─(unknown)──► [Luigi] ⚠️\n"
        "        └─(known)───► [Gianni] scope\n"
        "                         └─► [Chiara] build\n"
        "                               ├─► [TechAudit] ─┐\n"
        "                               ├─► [Compliance] ─┤ parallel\n"
        "                               └─► [Reputation] ─┘\n"
        "                               └─► [RiskPanel] aggregate\n"
        "                                     ├─(high)──► [Luigi] ⚠️\n"
        "                                     └─(ok)───► [Stacy QA]\n"
        "                                                   ├─(pass)─► [Marco]\n"
        "                                                   ├─(fail)─► [Chiara] retry\n"
        "                                                   └─(max)──► END\n"
        "                                                 [Marco] invoice\n"
        "                                                   └─► [Francesca] deliver\n"
        "                                                         └─► END",
        language=None,
    )

    st.divider()
    st.subheader("Pricing Table")
    for k, v in PRICING_TABLE.items():
        badge = f"€{v}" if v else "❓ unknown"
        st.markdown(f"- `{k}` → **{badge}**")

# ── Main ──────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("New Request")
    user_name = st.text_input("Client name", value="Michele")
    request = st.text_area(
        "What do you need?",
        placeholder="e.g. Build a Streamlit chatbot with OpenAI streaming",
        height=130,
    )

    sample_col1, sample_col2, sample_col3 = st.columns(3)
    with sample_col1:
        if st.button("🌐 Website"):
            request = "Create a premium Tailwind landing page for a law firm"
    with sample_col2:
        if st.button("🤖 Chatbot"):
            request = "Build a Streamlit chatbot app with OpenAI streaming"
    with sample_col3:
        if st.button("📊 Report"):
            request = "Write a strategic AI market entry report for Italy 2026"

    provider = st.selectbox("LLM Provider", ["anthropic", "openai"],
                             format_func=lambda p: {"anthropic": "🟣 Anthropic (Haiku + Sonnet)", "openai": "🟢 OpenAI (gpt-4o-mini + gpt-4o)"}[p])
    if provider == "anthropic":
        api_key = st.text_input("Anthropic API key", type="password",
                                 value=os.environ.get("ANTHROPIC_API_KEY", ""))
    else:
        api_key = st.text_input("OpenAI API key", type="password",
                                 value=os.environ.get("OPENAI_API_KEY", ""))
    run_btn = st.button("▶ Run Pipeline", type="primary",
                         disabled=not (request and api_key))

with col_right:
    st.subheader("Execution Trace")
    trace_placeholder = st.empty()

# ── Pipeline execution ─────────────────────────────────────────────────────────
AGENT_ICONS = {
    "Stacy":            "🎯",
    "Gianni":           "📐",
    "Chiara":           "🔨",
    "TechAuditor":      "🔒",
    "Compliance":       "⚖️",
    "Reputation":       "⭐",
    "RiskPanel":        "📊",
    "Stacy QA":         "✅",
    "Marco":            "💰",
    "Francesca":        "🚀",
    "Luigi":            "👑",
}


def parse_step(content: str) -> tuple[str, str]:
    if "]" in content and content.startswith("["):
        agent = content[1:content.index("]")]
        body  = content[content.index("]") + 1:].strip().lstrip("—").strip()
        return agent, body
    return "Agent", content


if run_btn and request and api_key:
    if provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
    else:
        os.environ["OPENAI_API_KEY"] = api_key

    from graph import run_pipeline

    graph_config = {"configurable": {"provider": provider}}
    accumulated: list[str] = []
    final_state = None

    with st.spinner("Pipeline running…"):
        try:
            steps, final_state = run_pipeline(request, user_name, config=graph_config)
            for step in steps:
                accumulated.append(step["content"])
        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.exception(exc)

    # Render trace
    with trace_placeholder.container():
        for line in accumulated:
            agent, body = parse_step(line)
            icon = AGENT_ICONS.get(agent, "🤖")
            st.markdown(f"{icon} **{agent}** — {body}")

    # ── Results ────────────────────────────────────────────────────────────
    if final_state:
        st.divider()
        r1, r2, r3 = st.columns(3)

        with r1:
            st.subheader("Invoice")
            if final_state.get("invoice"):
                inv = final_state["invoice"]
                st.metric("Price", f"€{inv['price_eur']:.2f}")
                st.json(inv)
            elif final_state.get("escalate_to_luigi"):
                st.warning(f"Escalated to Luigi: {final_state.get('escalation_reason')}")

        with r2:
            st.subheader("Risk Panel")
            score = final_state.get("aggregate_risk_score", 0)
            passed = final_state.get("risk_passed", True)
            color = "normal" if passed else "inverse"
            st.metric("Aggregate Risk", f"{score:.1f}/5", delta="PASS" if passed else "FAIL", delta_color=color)
            for rpt in final_state.get("risk_reports", []):
                with st.expander(rpt.get("agent", "agent")):
                    st.json(rpt)

        with r3:
            st.subheader("Delivery")
            dr = final_state.get("delivery_result")
            if dr:
                st.success(f"Status: {dr.get('status')}")
                st.json(dr)

        if final_state.get("deliverable_content"):
            with st.expander("Generated Deliverable (first 3000 chars)", expanded=False):
                st.code(final_state["deliverable_content"][:3000], language="python")
