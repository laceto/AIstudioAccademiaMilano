"""
Studio Digital Twin — Streamlit simulation interface.

Usage:
  streamlit run deliverables/2026-05-25_019_studio-digital-twin/streamlit_app.py

Env vars required (Streamlit Secrets or .env):
  ANTHROPIC_API_KEY  or  OPENAI_API_KEY
"""
import json
import sys
from pathlib import Path

import streamlit as st

# works whether launched from repo root or from within the deliverable folder
_here = Path(__file__).parent
sys.path.insert(0, str(_here))                    # flat imports from this package
sys.path.insert(0, str(_here.parent.parent))      # repo root (for config/ etc.)

from event_library import EVENTS, event_labels        # noqa: E402
from graph import run_simulation                       # noqa: E402
from studio_loader import load_studio_baseline        # noqa: E402

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Studio Digital Twin",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── helpers ───────────────────────────────────────────────────────────────────

_SEVERITY_COLOR = {1: "green", 2: "green", 3: "orange", 4: "red", 5: "red"}
_SEVERITY_LABEL = {1: "Negligible", 2: "Low", 3: "Moderate", 4: "High", 5: "Critical"}

def _severity_badge(s: int | float) -> str:
    si = max(1, min(5, round(float(s))))
    color = _SEVERITY_COLOR[si]
    label = _SEVERITY_LABEL[si]
    return f":{color}[**{si}/5 — {label}**]"

def _resilience_bar(score: float) -> str:
    filled = int(score)
    bar    = "█" * filled + "░" * (10 - filled)
    return f"`{bar}` {score:.1f}/10"

def _delta_str(val: float) -> str:
    if val > 0:
        return f"+€{val:,.2f}"
    return f"-€{abs(val):,.2f}"

# ── sidebar: studio baseline ───────────────────────────────────────────────────

with st.sidebar:
    st.title("🏭 Studio Digital Twin")
    st.caption("AI Studio Accademia Milano — simulation engine")
    st.divider()

    st.subheader("Current Studio State")
    try:
        baseline = load_studio_baseline()
        st.metric("Total requests processed", baseline["total_requests_processed"])
        st.metric("Total revenue",            f"€{baseline['total_revenue_eur']:,.2f}")
        st.metric("Avg revenue / request",    f"€{baseline['avg_revenue_per_request_eur']:,.2f}")
        st.metric("Skills",                   baseline["skills_count"])
        st.metric("Pipeline health",          f"{baseline['pipeline_health_pct']}%")
        st.metric("Team size",                baseline["team_size"])
        st.metric("Open P1 issues",           baseline["open_p1_issues"])
    except Exception as exc:
        st.error(f"Could not load baseline: {exc}")
        baseline = {}

    st.divider()
    provider = st.selectbox("LLM Provider", ["anthropic", "openai"], index=0)

# ── main area ─────────────────────────────────────────────────────────────────

st.title("Digital Twin Simulation")
st.markdown(
    "Inject an external event into the AI Studio's digital twin and observe "
    "how each department responds. The simulation runs in parallel across all "
    "five pipeline agents and synthesizes a consolidated impact report."
)

# ── event selector ────────────────────────────────────────────────────────────

col_event, col_custom = st.columns([1, 1])

with col_event:
    st.subheader("Event Library")
    labels     = event_labels()
    label_list = list(labels.values())
    key_list   = list(labels.keys())

    selected_label = st.selectbox("Select a pre-built event", label_list)
    selected_key   = key_list[label_list.index(selected_label)]
    selected_event = EVENTS[selected_key]

    st.markdown(f"**{selected_event['title']}**")
    st.caption(selected_event["description"])
    st.markdown(f"Severity: {_severity_badge(round(selected_event['severity'] * 5))}")

    use_custom = st.checkbox("Override with custom event JSON")

with col_custom:
    st.subheader("Custom Event (optional)")
    custom_json_str = st.text_area(
        "Paste custom event JSON",
        value=json.dumps(selected_event, indent=2),
        height=260,
        disabled=not use_custom,
    )

# ── resolve final event ────────────────────────────────────────────────────────

if use_custom:
    try:
        final_event = json.loads(custom_json_str)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
        st.stop()
else:
    final_event = selected_event

# ── run simulation ─────────────────────────────────────────────────────────────

st.divider()

if st.button("Run Simulation", type="primary", use_container_width=True):
    config = {"configurable": {"provider": provider}}

    progress_placeholder = st.empty()
    status_placeholder   = st.empty()

    dept_placeholders: dict[str, st.delta_generator.DeltaGenerator] = {}
    dept_cols = st.columns(5)
    dept_names = ["stacy_sim", "gianni_sim", "chiara_sim", "marco_sim", "francesca_sim"]
    dept_labels = {
        "stacy_sim":     "Stacy\nOrchestrator",
        "gianni_sim":    "Gianni\nScoper",
        "chiara_sim":    "Chiara\nBuilder",
        "marco_sim":     "Marco\nFinance",
        "francesca_sim": "Francesca\nDelivery",
    }
    for i, dept in enumerate(dept_names):
        with dept_cols[i]:
            dept_placeholders[dept] = st.empty()
            dept_placeholders[dept].info(f"⏳ {dept_labels[dept]}\n\n*waiting...*")

    completed_depts: set[str] = set()
    final_report: dict | None = None

    with st.spinner("Simulation running — all departments in parallel..."):
        try:
            steps, _ = run_simulation(final_event, studio_baseline=baseline, config=config)
        except Exception as exc:
            st.error(f"Simulation failed: {exc}")
            st.stop()

    # parse steps for department outputs and final report
    for step in steps:
        for node_name, node_output in step.items():
            if node_name in dept_names and node_name not in completed_depts:
                impacts = node_output.get("department_impacts", [])
                if impacts:
                    imp   = impacts[-1]
                    sev   = imp.get("severity", 3)
                    color = _SEVERITY_COLOR.get(sev, "orange")
                    label = dept_labels[node_name]
                    dept_placeholders[node_name].success(
                        f"**{label}**\n\n"
                        f"Severity: {sev}/5\n\n"
                        f"{imp.get('impact_summary', '')[:120]}..."
                    )
                    completed_depts.add(node_name)

            if node_name == "synthesizer":
                report = node_output.get("simulation_report")
                if report:
                    final_report = report

    # mark any still-waiting departments
    for dept in dept_names:
        if dept not in completed_depts:
            dept_placeholders[dept].warning(f"**{dept_labels[dept]}**\n\nNo output captured.")

    # ── final report ──────────────────────────────────────────────────────────

    if not final_report:
        st.warning("Simulation completed but no synthesis report was generated.")
        st.stop()

    st.divider()
    st.subheader("Simulation Report")

    # header metrics
    m1, m2, m3, m4 = st.columns(4)
    sev_val = final_report.get("overall_severity", 0)
    m1.metric("Overall Severity",      f"{sev_val:.1f}/5")
    m2.metric("Resilience Score",      f"{final_report.get('resilience_score', 0):.1f}/10")
    m3.metric("Time to Recover",       f"{final_report.get('time_to_recover_days', '?')} days")
    fin = final_report.get("financial_impact", {})
    m4.metric(
        "Margin Delta",
        f"{fin.get('margin_delta_pct', 0):+.1f}%",
        delta_color="inverse",
    )

    # narrative
    st.markdown(f"**Summary:** {final_report.get('narrative', '')}")

    # financial breakdown
    with st.expander("Financial Impact", expanded=True):
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("Revenue delta",  _delta_str(fin.get("revenue_delta_eur", 0)))
        fc2.metric("Cost delta",     _delta_str(fin.get("cost_delta_eur", 0)))
        fc3.metric("Margin delta %", f"{fin.get('margin_delta_pct', 0):+.1f}%")

    # bottlenecks
    bottlenecks = final_report.get("bottlenecks", [])
    if bottlenecks:
        with st.expander("Bottlenecks", expanded=True):
            for b in bottlenecks:
                st.markdown(f"- {b}")

    # recommended actions
    actions = final_report.get("recommended_actions", [])
    if actions:
        with st.expander("Recommended Actions", expanded=True):
            for a in sorted(actions, key=lambda x: x.get("priority", 99)):
                pri  = a.get("priority", "?")
                act  = a.get("action", "")
                own  = a.get("owner", "")
                time = a.get("timeline", "")
                st.markdown(f"**{pri}.** {act}  \n`{own}` — {time}")

    # upsides
    upsides = final_report.get("upsides", [])
    if upsides:
        with st.expander("Silver Linings"):
            for u in upsides:
                st.markdown(f"- {u}")

    # department details
    with st.expander("Department Detail"):
        for imp in final_report.get("department_details", []):
            dept = imp.get("department", "?").capitalize()
            sev  = imp.get("severity", 3)
            st.markdown(
                f"**{dept}** — Severity {sev}/5  \n"
                f"{imp.get('impact_summary', '')}  \n"
                f"*Action:* {imp.get('recommended_action', '')}  \n"
                f"*Financial delta:* {_delta_str(imp.get('financial_delta_eur', 0))}"
            )
            st.divider()

    # resilience bar
    st.markdown(
        f"**Resilience:** {_resilience_bar(final_report.get('resilience_score', 5))}"
    )

    # disclaimer
    st.caption(
        final_report.get(
            "disclaimer",
            "Simulation output — not a prediction or professional advice.",
        )
    )

    # raw JSON export
    with st.expander("Export raw JSON"):
        st.json(final_report)
        st.download_button(
            "Download report.json",
            data=json.dumps(final_report, indent=2, ensure_ascii=False),
            file_name="twin_simulation_report.json",
            mime="application/json",
        )
