"""
Avvocato AI — LangGraph state definition.
Designed for Michele's father's law firm (Italian jurisdiction).
"""
from __future__ import annotations
import operator
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# ── Domain constants ──────────────────────────────────────────────────────────

MATTER_TYPES = {
    "penale":       "Diritto Penale",
    "civile":       "Diritto Civile",
    "contrattuale": "Diritto Contrattuale",
    "societario":   "Diritto Societario / Commerciale",
    "famiglia":     "Diritto di Famiglia",
    "immobiliare":  "Diritto Immobiliare",
    "lavoro":       "Diritto del Lavoro",
    "unknown":      "Da classificare",
}

_BILLING_RATES_FALLBACK = {
    "penale":       {"hourly": 350.0, "min_hours": 2.0},
    "civile":       {"hourly": 250.0, "min_hours": 1.0},
    "contrattuale": {"hourly": 280.0, "min_hours": 1.5},
    "societario":   {"hourly": 400.0, "min_hours": 2.0},
    "famiglia":     {"hourly": 200.0, "min_hours": 1.0},
    "immobiliare":  {"hourly": 220.0, "min_hours": 1.0},
    "lavoro":       {"hourly": 230.0, "min_hours": 1.0},
    "unknown":      {"hourly": 250.0, "min_hours": 1.0},
}


def _load_billing_rates() -> dict:
    import json
    from pathlib import Path
    try:
        cfg = Path(__file__).resolve().parents[2] / "config" / "global_settings.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        loaded = data.get("lawyer_billing_rates", {})
        return loaded if loaded else _BILLING_RATES_FALLBACK
    except Exception:
        return _BILLING_RATES_FALLBACK


BILLING_RATES: dict = _load_billing_rates()

DISCLAIMER_IT = (
    "⚠️ AVVERTENZA LEGALE: Il presente documento ha carattere esclusivamente "
    "informativo e non costituisce consulenza legale specifica né instaura un "
    "rapporto professionale tra l'utente e lo studio legale. Per assistenza "
    "legale specifica al suo caso, contattare direttamente l'Avvocato."
)

CONTACT_METHODS = ["email", "discord", "whatsapp", "portale_sicuro"]


class LawyerState(TypedDict):
    # ── Client input ─────────────────────────────────────────────────────
    client_request: str
    client_name: str
    contact_method: str          # email | discord | whatsapp | portale_sicuro

    # ── Intake ───────────────────────────────────────────────────────────
    matter_type: Optional[str]   # key from MATTER_TYPES
    urgency: Optional[str]       # urgente | standard | bassa_priorita
    jurisdiction: Optional[str]  # IT | EU | other
    intake_summary: Optional[str]

    # ── Legal Research ───────────────────────────────────────────────────
    legal_research: Optional[dict]
    relevant_articles: Optional[List[str]]
    relevant_cases: Optional[List[str]]
    research_confidence: Optional[float]

    # ── Document Drafting ─────────────────────────────────────────────────
    draft_document: Optional[str]
    document_type: Optional[str]  # parere | contratto | atto | lettera | clausola
    disclaimer_included: bool

    # ── Parallel QA checks (via Send) ────────────────────────────────────
    review_reports: Annotated[List[dict], operator.add]

    # ── QA merge ─────────────────────────────────────────────────────────
    qa_passed: bool
    qa_issues: Optional[List[str]]

    # ── Billing ──────────────────────────────────────────────────────────
    billing_type: Optional[str]   # orario | forfettario | success_fee
    hourly_rate: Optional[float]
    estimated_hours: Optional[float]
    total_fee: Optional[float]
    invoice: Optional[dict]

    # ── Delivery ─────────────────────────────────────────────────────────
    delivery_result: Optional[dict]

    # ── LangChain message history ─────────────────────────────────────────
    messages: Annotated[List[BaseMessage], add_messages]

    # ── Control ───────────────────────────────────────────────────────────
    error: Optional[str]
    finished: bool
