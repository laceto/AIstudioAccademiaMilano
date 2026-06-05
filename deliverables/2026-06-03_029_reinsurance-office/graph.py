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

NOTE: interrupt_before=["branch_manager_approve"] fires unconditionally on every
execution. In auto_approve=True mode run_workflow() handles resume automatically
via update_state() + stream(None). Any caller that invokes branch_graph.stream()
directly must replicate this resume step, otherwise the graph stalls permanently.
"""
import uuid
from datetime import datetime
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
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
    """claim → actuarial_analyst; treaty → parallel_aggregator."""
    return "parallel_aggregator" if state.get("workflow_type") == "treaty" else "actuarial_analyst"


def route_after_actuarial(state: BranchState) -> str:
    """claim → accountant; treaty/report → parallel_aggregator."""
    return "accountant" if state.get("workflow_type", "claim") == "claim" else "parallel_aggregator"


def route_after_accountant(state: BranchState) -> str:
    """report (early via Send) → parallel_aggregator; claim/treaty → sr_accounting_exec."""
    return "parallel_aggregator" if state.get("workflow_type") == "report" else "sr_accounting_exec"


def route_after_aggregator(state: BranchState) -> str:
    """treaty → accountant; report → sr_accounting_exec (skips accountant)."""
    return "sr_accounting_exec" if state.get("workflow_type") == "report" else "accountant"


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

    # claim: MW → actuarial; treaty: MW → aggregator
    g.add_conditional_edges("medical_underwriter", route_after_medical)

    # claim: actuarial → accountant; treaty/report: actuarial → aggregator
    g.add_conditional_edges("actuarial_analyst", route_after_actuarial)

    # claim/treaty: accountant → sr_exec; report: accountant (early Send) → aggregator
    g.add_conditional_edges("accountant", route_after_accountant)

    # treaty: aggregator → accountant; report: aggregator → sr_exec
    g.add_conditional_edges("parallel_aggregator", route_after_aggregator)

    g.add_edge("sr_accounting_exec",     "branch_manager_approve")
    g.add_edge("branch_manager_approve", END)

    return g.compile(checkpointer=MemorySaver(), interrupt_before=["branch_manager_approve"])


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

    thread_id = case_id or f"CASE-{uuid.uuid4().hex[:8].upper()}"
    config = {
        "configurable": {
            "provider": provider,
            "auto_approve": auto_approve,
            "thread_id": thread_id,
        }
    }
    steps: list[dict] = []
    final_state: dict = {}

    for event in branch_graph.stream(initial, config=config, stream_mode="values"):
        msgs = event.get("messages", [])
        if msgs:
            last = msgs[-1]
            steps.append({"content": last.content, "snapshot": event})
        final_state = event

    # HITL: inject decision via update_state then resume (requires checkpointer)
    if not final_state.get("finished") and auto_approve:
        branch_graph.update_state(config, {"manager_decision": "approved"})
        for event in branch_graph.stream(None, config=config, stream_mode="values"):
            msgs = event.get("messages", [])
            if msgs:
                steps.append({"content": msgs[-1].content, "snapshot": event})
            final_state = event

    return steps, final_state
