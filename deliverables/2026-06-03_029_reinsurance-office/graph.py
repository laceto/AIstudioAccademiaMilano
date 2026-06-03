"""
Reinsurance Branch Office — LangGraph StateGraph assembly.

Three workflow paths share the same graph:

  claim:
    START → branch_manager_intake → medical_underwriter → actuarial_analyst
          → accountant → sr_accounting_exec → branch_manager_approve → END

  treaty:
    START → branch_manager_intake
          → [Send: medical_underwriter, actuarial_analyst]  (parallel)
          → parallel_aggregator → accountant → sr_accounting_exec
          → branch_manager_approve → END

  report:
    START → branch_manager_intake
          → [Send: actuarial_analyst, accountant]           (parallel)
          → parallel_aggregator → sr_accounting_exec
          → branch_manager_approve → END

Human-in-the-loop: branch_manager_approve is an interrupt node in production.
Set config["configurable"]["auto_approve"] = False to activate HITL.
"""
import uuid
from datetime import datetime
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .nodes import (
    accountant,
    actuarial_analyst,
    branch_manager_approve,
    branch_manager_intake,
    medical_underwriter,
    parallel_aggregator,
    sr_accounting_exec,
)
from .state import BranchState


# ── Routing ────────────────────────────────────────────────────────────────────

def route_after_intake(state: BranchState) -> list[Send] | str:
    wf = state.get("workflow_type", "claim")

    if wf == "claim":
        return "medical_underwriter"

    if wf == "treaty":
        return [
            Send("medical_underwriter", state),
            Send("actuarial_analyst",   state),
        ]

    # report: actuary + accountant in parallel
    return [
        Send("actuarial_analyst", state),
        Send("accountant",        state),
    ]


def route_after_medical(state: BranchState) -> str:
    return "actuarial_analyst"


def route_after_actuarial(state: BranchState) -> str:
    return "accountant"


def route_after_aggregator(state: BranchState) -> str:
    wf = state.get("workflow_type", "claim")
    return "sr_accounting_exec" if wf == "report" else "accountant"


def route_after_approve(state: BranchState) -> str:
    return END


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_branch_graph():
    g = StateGraph(BranchState)

    g.add_node("branch_manager_intake",  branch_manager_intake)
    g.add_node("medical_underwriter",    medical_underwriter)
    g.add_node("actuarial_analyst",      actuarial_analyst)
    g.add_node("parallel_aggregator",    parallel_aggregator)
    g.add_node("accountant",             accountant)
    g.add_node("sr_accounting_exec",     sr_accounting_exec)
    g.add_node("branch_manager_approve", branch_manager_approve)

    g.add_edge(START, "branch_manager_intake")

    # intake fans out differently per workflow type
    g.add_conditional_edges("branch_manager_intake", route_after_intake)

    # claim path: linear
    g.add_edge("medical_underwriter", "actuarial_analyst")
    g.add_edge("actuarial_analyst",   "accountant")

    # parallel paths converge at aggregator
    g.add_edge("parallel_aggregator", "accountant")

    # accountant always feeds sr exec (report path skips accountant → sr exec direct)
    g.add_edge("accountant",       "sr_accounting_exec")
    g.add_edge("sr_accounting_exec", "branch_manager_approve")
    g.add_edge("branch_manager_approve", END)

    return g.compile(interrupt_before=["branch_manager_approve"])


branch_graph = build_branch_graph()


# ── Public helper ──────────────────────────────────────────────────────────────

def run_workflow(
    case_input: str,
    workflow_type: str = "claim",
    case_id: str | None = None,
    provider: str = "anthropic",
    auto_approve: bool = True,
) -> tuple[list[dict], dict]:
    """Run a full workflow and return (steps, final_state)."""
    initial: BranchState = {
        "workflow_type":          workflow_type,
        "case_id":                case_id or f"CASE-{uuid.uuid4().hex[:8].upper()}",
        "case_input":             case_input,
        "intake_summary":         None,
        "manager_decision":       None,
        "escalation_reason":      None,
        "medical_assessment":     None,
        "actuarial_assessment":   None,
        "accounting_entries":     None,
        "financial_report":       None,
        "parallel_reports":       [],
        "awaiting_approval":      False,
        "approval_requested_from": None,
        "final_output":           None,
        "case_status":            None,
        "messages":               [],
        "error":                  None,
        "finished":               False,
    }

    config = {"configurable": {"provider": provider, "auto_approve": auto_approve}}
    steps: list[dict] = []
    final_state: dict = {}

    for event in branch_graph.stream(initial, config=config, stream_mode="values"):
        msgs = event.get("messages", [])
        if msgs:
            last = msgs[-1]
            steps.append({"content": last.content, "snapshot": event})
        final_state = event

    # HITL: if interrupted at approval gate, resume with auto_approve
    if not final_state.get("finished") and auto_approve:
        final_state["manager_decision"] = "approved"
        for event in branch_graph.stream(
            None, config=config, stream_mode="values"
        ):
            msgs = event.get("messages", [])
            if msgs:
                steps.append({"content": msgs[-1].content, "snapshot": event})
            final_state = event

    return steps, final_state
