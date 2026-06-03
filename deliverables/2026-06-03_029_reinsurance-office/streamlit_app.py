"""
Reinsurance Branch Office — Streamlit App
Tabs: Team Showcase | Run Workflow | Case Log
"""
import json
import os
import uuid
from datetime import datetime

import streamlit as st

st.set_page_config(
    page_title="Reinsurance Branch Office",
    page_icon="🏦",
    layout="wide",
)

# ── Team data ──────────────────────────────────────────────────────────────────

TEAM = [
    {
        "title": "Principal Officer / Branch Manager",
        "icon": "👔",
        "color": "#1a3a5c",
        "responsibilities": [
            "Receives and routes all incoming cases",
            "Final approval authority on claims, treaties, reports",
            "Human-in-the-loop gate before sign-off",
            "Escalates P1 regulatory flags",
        ],
        "tools": ["LangGraph HITL interrupt", "case routing", "approval sign-off"],
        "tier": "fast",
    },
    {
        "title": "Sr Accounting Executive",
        "icon": "📊",
        "color": "#2e6da4",
        "responsibilities": [
            "Consolidates P&L from all specialist inputs",
            "Prepares management and regulatory reports",
            "Signs off on financial statements",
            "Flags regulatory exposure to compliance",
        ],
        "tools": ["P&L consolidation", "regulatory reporting", "treaty accounting"],
        "tier": "smart",
    },
    {
        "title": "Actuarial Analyst",
        "icon": "📐",
        "color": "#c0392b",
        "responsibilities": [
            "Calculates loss ratios, IBNR reserves",
            "Pricing adequacy checks (flag < 0.85)",
            "Risk Units: P(event) × impact × blast_radius",
            "Trend analysis for monthly reports",
        ],
        "tools": ["loss triangle", "IBNR modelling", "pricing adequacy", "RU scoring"],
        "tier": "smart",
    },
    {
        "title": "Accountant",
        "icon": "📒",
        "color": "#27ae60",
        "responsibilities": [
            "Processes bordereaux entries",
            "Books reserve movements",
            "Premium and claim accounting",
            "Reconciles treaty settlements",
        ],
        "tools": ["bordereaux", "reserve movements", "double-entry bookkeeping"],
        "tier": "fast",
    },
    {
        "title": "Medical Underwriter / Claim Analyst",
        "icon": "🏥",
        "color": "#8e44ad",
        "responsibilities": [
            "Underwrites medical risks in life/health treaties",
            "Validates incoming claims (diagnosis flags)",
            "Recommends claim reserves",
            "Flags high-risk portfolios",
        ],
        "tools": ["claim validity check", "diagnosis flags", "reserve recommendation"],
        "tier": "smart",
    },
]

WORKFLOWS = {
    "claim": {
        "label": "Claim Processing",
        "icon": "📋",
        "description": "Process an incoming reinsurance claim end-to-end.",
        "flow": ["Branch Manager", "Medical UW", "Actuarial", "Accountant", "Sr Exec", "Approval"],
        "example": (
            "Life reinsurance claim: insured male, age 54, death benefit €200,000. "
            "Cause: acute myocardial infarction. Policy in force 7 years. "
            "Original insurer (cedant) requesting full reinsurance payout per treaty XYZ-2019."
        ),
    },
    "treaty": {
        "label": "Treaty Evaluation",
        "icon": "📜",
        "description": "Evaluate and price a new reinsurance treaty proposal.",
        "flow": ["Branch Manager", "Medical UW ∥ Actuarial", "Accountant", "Sr Exec", "Approval"],
        "example": (
            "New quota-share treaty proposal from Assicurazioni Meridionali. "
            "Portfolio: 1,200 individual life policies, avg sum insured €150,000, "
            "age band 35-60, cession rate 40%. Requesting 3-year term with annual review."
        ),
    },
    "report": {
        "label": "Monthly Reporting",
        "icon": "📅",
        "description": "Run the monthly actuarial and financial reporting cycle.",
        "flow": ["Branch Manager", "Actuarial ∥ Accountant", "Sr Exec", "Approval"],
        "example": (
            "Monthly reporting cycle — May 2026. Portfolio: 14 active treaties. "
            "Total ceded premium YTD: €1.2M. Claims paid YTD: €340,000. "
            "3 IBNR items pending. Regulatory IVASS report due 15th June."
        ),
    },
}

# ── Session state ──────────────────────────────────────────────────────────────

if "case_log" not in st.session_state:
    st.session_state.case_log = []

# ── Header ─────────────────────────────────────────────────────────────────────

st.title("🏦 Reinsurance Branch Office")
st.caption("AI-assisted multi-agent system — LangGraph · 5 specialist agents")

tab_team, tab_run, tab_log = st.tabs(["👥 Team", "⚙️ Run Workflow", "📂 Case Log"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Team Showcase
# ══════════════════════════════════════════════════════════════════════════════

with tab_team:
    st.subheader("Branch Team")
    st.caption("Five specialist agents collaborating through a LangGraph state machine.")

    cols = st.columns([1, 1, 1, 1, 1])
    for i, member in enumerate(TEAM):
        with cols[i]:
            st.markdown(
                f"""<div style="background:{member['color']};border-radius:12px;padding:16px;color:white;min-height:260px;">
                <div style="font-size:2.2rem;text-align:center">{member['icon']}</div>
                <div style="font-weight:700;font-size:0.85rem;text-align:center;margin:8px 0">{member['title']}</div>
                <hr style="border-color:rgba(255,255,255,0.3)">
                {''.join(f'<div style="font-size:0.72rem;margin:3px 0">• {r}</div>' for r in member['responsibilities'])}
                <hr style="border-color:rgba(255,255,255,0.3)">
                <div style="font-size:0.68rem;opacity:0.85">LLM: {"⚡ fast" if member["tier"]=="fast" else "🧠 smart"}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.divider()
    st.subheader("Workflow Paths")
    for wf_key, wf in WORKFLOWS.items():
        with st.expander(f"{wf['icon']} {wf['label']}"):
            st.markdown(f"**Flow:** {' → '.join(wf['flow'])}")
            st.markdown(wf["description"])

    st.divider()
    st.subheader("Graph Architecture")
    st.code("""
START → branch_manager_intake
  ├─(claim)──► medical_underwriter → actuarial_analyst
  │             → accountant → sr_accounting_exec
  │             → branch_manager_approve [HITL] → END
  │
  ├─(treaty)─► Send(medical_underwriter) ∥ Send(actuarial_analyst)
  │             → parallel_aggregator → accountant
  │             → sr_accounting_exec → branch_manager_approve [HITL] → END
  │
  └─(report)─► Send(actuarial_analyst) ∥ Send(accountant)
                → parallel_aggregator → sr_accounting_exec
                → branch_manager_approve [HITL] → END
    """, language="text")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Run Workflow
# ══════════════════════════════════════════════════════════════════════════════

with tab_run:
    st.subheader("Submit a Case")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        workflow_key = st.selectbox(
            "Workflow type",
            options=list(WORKFLOWS.keys()),
            format_func=lambda k: f"{WORKFLOWS[k]['icon']} {WORKFLOWS[k]['label']}",
        )
        wf = WORKFLOWS[workflow_key]
        st.caption(wf["description"])

        provider = st.radio("LLM Provider", ["anthropic", "openai"], horizontal=True)
        auto_approve = st.checkbox("Auto-approve (Branch Manager)", value=True)

        if st.button("Load example", type="secondary"):
            st.session_state["case_input_text"] = wf["example"]

        case_input = st.text_area(
            "Case submission",
            value=st.session_state.get("case_input_text", ""),
            height=180,
            key="case_input_widget",
            placeholder="Describe the case, claim, or treaty details...",
        )

    with col_right:
        st.markdown("**Pipeline flow:**")
        for step in wf["flow"]:
            st.markdown(f"→ {step}")

        api_key_set = bool(
            os.getenv("ANTHROPIC_API_KEY") if provider == "anthropic"
            else os.getenv("OPENAI_API_KEY")
        )
        if not api_key_set:
            st.warning(
                f"Set `{'ANTHROPIC_API_KEY' if provider == 'anthropic' else 'OPENAI_API_KEY'}` "
                "in your environment or Streamlit Secrets to run the live workflow.",
                icon="⚠️",
            )

    if st.button("▶ Run Workflow", type="primary", disabled=not case_input.strip()):
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        progress_area = st.empty()
        log_area = st.empty()
        steps_display = []

        with st.spinner(f"Running {wf['label']} — {case_id} ..."):
            try:
                from .graph import run_workflow

                steps, final_state = run_workflow(
                    case_input=case_input,
                    workflow_type=workflow_key,
                    case_id=case_id,
                    provider=provider,
                    auto_approve=auto_approve,
                )

                for s in steps:
                    steps_display.append(s["content"])
                    log_area.markdown("\n\n".join(
                        f"`{line}`" for line in steps_display
                    ))

                st.success(f"✅ Case {case_id} — {final_state.get('case_status', '?').upper()}")

                if final_output := final_state.get("final_output"):
                    st.subheader("Final Decision")
                    st.text(final_output)

                if report := final_state.get("financial_report"):
                    with st.expander("📊 Financial Report"):
                        st.json(report)

                if actuarial := final_state.get("actuarial_assessment"):
                    with st.expander("📐 Actuarial Assessment"):
                        st.json(actuarial)

                if medical := final_state.get("medical_assessment"):
                    with st.expander("🏥 Medical Assessment"):
                        st.json(medical)

                # Add to case log
                st.session_state.case_log.append({
                    "case_id": case_id,
                    "workflow": wf["label"],
                    "status": final_state.get("case_status", "unknown"),
                    "pl_impact": (final_state.get("financial_report") or {}).get("pl_impact", "N/A"),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })

            except ImportError:
                st.error("Install dependencies: `pip install -r requirements.txt`")
            except Exception as exc:
                st.error(f"Error: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Case Log
# ══════════════════════════════════════════════════════════════════════════════

with tab_log:
    st.subheader("Case Log")

    if not st.session_state.case_log:
        st.info("No cases processed yet. Run a workflow in the ⚙️ tab.")
    else:
        import pandas as pd
        df = pd.DataFrame(st.session_state.case_log)
        st.dataframe(df, use_container_width=True)

        approved = sum(1 for c in st.session_state.case_log if c["status"] == "approved")
        total = len(st.session_state.case_log)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total cases", total)
        c2.metric("Approved", approved)
        c3.metric("Approval rate", f"{approved/total*100:.0f}%" if total else "—")

        if st.button("Clear log"):
            st.session_state.case_log = []
            st.rerun()
