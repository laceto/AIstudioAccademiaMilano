"""Reinsurance Branch Office — shared LangGraph state."""
from __future__ import annotations
import operator
from typing import Annotated, List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


WorkflowType = Literal["claim", "treaty", "report"]


class BranchState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────
    workflow_type: WorkflowType       # claim | treaty | report
    case_id: str
    case_input: str                   # raw submission text

    # ── Branch Manager ───────────────────────────────────────────────────
    intake_summary: Optional[str]     # structured intake from manager
    manager_decision: Optional[str]   # approved | rejected | pending
    escalation_reason: Optional[str]

    # ── Medical Underwriter / Claim Analyst ──────────────────────────────
    medical_assessment: Optional[dict]
    # keys: risk_level (low|medium|high), diagnosis_flags, claim_validity,
    #       recommended_reserve, notes

    # ── Actuarial Analyst ────────────────────────────────────────────────
    actuarial_assessment: Optional[dict]
    # keys: loss_ratio, ibnr_reserve, pricing_adequacy, risk_units, notes

    # ── Accountant ───────────────────────────────────────────────────────
    accounting_entries: Optional[dict]
    # keys: debit, credit, reserve_movement, net_impact, currency

    # ── Sr Accounting Executive ──────────────────────────────────────────
    financial_report: Optional[dict]
    # keys: summary, pl_impact, regulatory_flags, sign_off_ready

    # ── Parallel fan-out accumulator ─────────────────────────────────────
    parallel_reports: Annotated[List[dict], operator.add]

    # ── Human-in-the-loop ────────────────────────────────────────────────
    awaiting_approval: bool
    approval_requested_from: Optional[str]  # "branch_manager"

    # ── Output ───────────────────────────────────────────────────────────
    final_output: Optional[str]
    case_status: Optional[str]        # open | approved | rejected | pending_info

    # ── LangChain messages ───────────────────────────────────────────────
    messages: Annotated[List[BaseMessage], add_messages]

    # ── Control ──────────────────────────────────────────────────────────
    error: Optional[str]
    finished: bool
