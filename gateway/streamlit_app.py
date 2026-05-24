"""
gateway/streamlit_app.py — Sofia (Frontend/UX Engineer)

User-facing Streamlit form that submits requests to the 6-agent pipeline
via PipelineAdapter. No agent names or JSON exposed to the user.

Run:
  streamlit run gateway/streamlit_app.py
"""

import time
from pathlib import Path

import streamlit as st
import yaml

from gateway.pipeline_adapter import PipelineAdapter

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Studio Accademia Milano",
    page_icon="🎓",
    layout="centered",
)

# ── Intent registry (optional dropdown) ─────────────────────────────────────

_INTENT_REGISTRY_PATH = Path("process/intent_registry.yaml")

_FALLBACK_INTENTS = {
    "I want a website": "website_creation",
    "I need a PDF document": "pdf_generation",
    "I need an invoice": "invoice_generation",
    "I want a chatbot": "chatbot_app",
    "I need a strategic report": "strategic_report",
    "I want to set up email automation": "email_delivery",
    "Other (describe below)": "unknown",
}


@st.cache_data
def load_intents() -> dict[str, str]:
    if _INTENT_REGISTRY_PATH.exists():
        raw = yaml.safe_load(_INTENT_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
        return {k.replace("_", " ").title(): k for k in raw.keys()} or _FALLBACK_INTENTS
    return _FALLBACK_INTENTS


# ── Pipeline stage labels (plain language, no agent names) ───────────────────

_STAGES = [
    "Analyzing your request...",
    "Planning the solution...",
    "Building your deliverable...",
    "Checking quality...",
    "Preparing your invoice...",
    "Delivering...",
]

# ── Session state ────────────────────────────────────────────────────────────

if "history" not in st.session_state:
    st.session_state.history = []   # list of {text, status, job_id, result}

# ── Sidebar: history ─────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Recent requests")
    if st.session_state.history:
        for entry in reversed(st.session_state.history[-5:]):
            badge = "✅" if entry["status"] == "queued" else "❌"
            st.markdown(f"{badge} `{entry['job_id']}` — {entry['text'][:40]}...")
    else:
        st.caption("No requests yet.")

# ── Main form ────────────────────────────────────────────────────────────────

st.title("AI Studio Accademia Milano")
st.caption("Tell us what you need — we'll build it.")

intents = load_intents()
intent_label = st.selectbox(
    "What do you need?",
    options=list(intents.keys()),
    index=len(intents) - 1,
)

user_text = st.text_area(
    "Describe your request",
    placeholder="e.g. I need a landing page for my bakery in Milan...",
    height=140,
)

submitted = st.button("Submit request", type="primary", use_container_width=True)

# ── On submit ────────────────────────────────────────────────────────────────

if submitted:
    full_text = user_text.strip()
    if not full_text:
        st.error("Please describe your request before submitting.")
        st.stop()

    selected_intent = intents[intent_label]
    combined = f"[Intent: {selected_intent}] {full_text}" if selected_intent != "unknown" else full_text

    adapter = PipelineAdapter()

    with st.status("Processing your request...", expanded=True) as status_widget:
        for stage in _STAGES:
            st.write(stage)
            time.sleep(0.4)

        result = adapter.submit(
            text=combined,
            channel="streamlit",
            metadata={"intent_label": intent_label},
        )

        if result["status"] == "error":
            status_widget.update(label="Something went wrong", state="error")
            st.error(result["result"])
        else:
            status_widget.update(label="Request received!", state="complete")

    if result["status"] == "queued":
        st.success(f"Your request has been queued. Job ID: `{result['job_id']}`")
        st.info("You'll be notified when your deliverable is ready. Check back soon.")

        st.session_state.history.append({
            "job_id": result["job_id"],
            "text": full_text,
            "status": "queued",
            "result": None,
        })

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Submit another request", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Check job status", use_container_width=True):
            st.info(f"Use job ID `{result.get('job_id', '—')}` to check status via the API.")
