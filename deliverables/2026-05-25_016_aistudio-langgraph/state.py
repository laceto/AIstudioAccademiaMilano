"""
AI Studio Accademia Milano — LangGraph state definition.
Single source of truth for all agent data flowing through the pipeline.
"""
from __future__ import annotations
import operator
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

_PRICING_FALLBACK: dict[str, Optional[str]] = {
    "static_landing_page":     "9.90",
    "premium_landing_page":    "29.90",
    "commercial_landing_page": "45.90",
    "pdf_document":            "1.90",
    "invoice_pdf":             "3.90",
    "strategic_report":        "4.90",
    "chatbot_app":             "19.90",
    "email_delivery":          "0.50",
    "rag_knowledge_base":      "29.90",
    "calendar_integration":    "14.90",
    "weather_dashboard":       "9.90",
    "agent_deploy_streamlit":  "19.90",
    "algo_trading":            "24.90",
    "mind_dashboard_journal":  "9.90",
    "micro_syllabus_flashcards": "14.90",
    "family_archivist":        "14.90",
    "mediterranean_meal_planner": "14.90",
    "niccolo_chronicles":      "14.90",
    "unknown_product":         None,
}


def _load_pricing() -> dict[str, Optional[str]]:
    import json
    from pathlib import Path
    try:
        cfg = Path(__file__).resolve().parents[2] / "config" / "global_settings.json"
        raw = json.loads(cfg.read_text(encoding="utf-8"))
        loaded: dict[str, Optional[str]] = {}
        for k, v in raw.get("pricing", {}).items():
            if v is None:
                loaded[k] = None
            else:
                loaded[k] = str(v).lstrip("€")
        # Merge: fallback provides defaults; JSON overrides; null_product always None
        merged = {**_PRICING_FALLBACK, **loaded}
        merged["unknown_product"] = None
        return merged
    except Exception:
        return _PRICING_FALLBACK


PRICING_TABLE: dict[str, Optional[str]] = _load_pricing()


class StudioState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────
    request: str
    user_name: str
    input_type: str                  # text | voice | qr

    # ── Stacy Step 1 ─────────────────────────────────────────────────────
    intent: Optional[str]
    product_type: Optional[str]
    dependencies_ok: bool

    # ── Gianni ───────────────────────────────────────────────────────────
    technical_spec: Optional[dict]
    stack: Optional[List[str]]
    deployment_target: Optional[str]
    estimated_hours: Optional[float]
    blockers: Optional[List[str]]

    # ── Chiara ───────────────────────────────────────────────────────────
    deliverable_content: Optional[str]
    deliverable_path: Optional[str]
    skills_used: Optional[List[str]]
    qa_iteration: int

    # ── Risk Panel (parallel fan-out via Send) ────────────────────────────
    risk_reports: Annotated[List[dict], operator.add]   # accumulated by all 3 agents
    risk_passed: bool
    aggregate_risk_score: float

    # ── Stacy QA ─────────────────────────────────────────────────────────
    qa_result: Optional[dict]
    qa_passed: bool

    # ── Marco ────────────────────────────────────────────────────────────
    product_price: Optional[str]
    invoice: Optional[dict]
    invoice_id: Optional[str]

    # ── Francesca ────────────────────────────────────────────────────────
    user_email: Optional[str]
    delivery_result: Optional[dict]
    audit_log_path: Optional[str]

    # ── Luigi (human-in-the-loop escalation) ─────────────────────────────
    escalate_to_luigi: bool
    luigi_decision: Optional[str]    # approved | rejected
    escalation_reason: Optional[str]

    # ── LangChain message history ─────────────────────────────────────────
    messages: Annotated[List[BaseMessage], add_messages]

    # ── Control ───────────────────────────────────────────────────────────
    # Annotated so parallel risk agents can each write error without conflict
    error: Annotated[Optional[str], lambda a, b: b if b is not None else a]
    finished: bool
