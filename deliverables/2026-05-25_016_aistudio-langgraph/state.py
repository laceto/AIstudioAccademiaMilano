"""
AI Studio Accademia Milano — LangGraph state definition.
Single source of truth for all agent data flowing through the pipeline.
"""
from __future__ import annotations
import operator
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

PRICING_TABLE: dict[str, Optional[str]] = {
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
}


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
    error: Optional[str]
    finished: bool
