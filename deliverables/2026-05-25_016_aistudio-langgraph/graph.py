"""
AI Studio Accademia Milano — LangGraph StateGraph assembly.

Pipeline:
  START → stacy_classify
            ├─(unknown)──► luigi_escalate ──► (approved) → gianni_scope | (rejected) → END
            └─(known)───► gianni_scope
                            └─► chiara_implement
                                  └─► [Send: technical_auditor, compliance_agent, reputation_guardian]
                                        └─► risk_aggregator
                                              ├─(high risk)──► luigi_escalate
                                              └─(ok)─────► stacy_qa
                                                              ├─(pass)────────────────► marco_invoice
                                                              ├─(fail, retry < 3)──► chiara_implement
                                                              └─(fail, max retries)─► END
                                                            marco_invoice
                                                              └─► francesca_deliver
                                                                    └─► END
"""
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .nodes import (
    chiara_implement,
    compliance_agent,
    francesca_deliver,
    gianni_scope,
    luigi_escalate,
    marco_invoice,
    reputation_guardian,
    risk_aggregator,
    stacy_classify,
    stacy_qa,
    technical_auditor,
)
from .state import StudioState


# ── Routing functions ──────────────────────────────────────────────────────────

def route_after_classify(state: StudioState) -> Literal["luigi_escalate", "gianni_scope"]:
    return "luigi_escalate" if state.get("escalate_to_luigi") else "gianni_scope"


def dispatch_risk_agents(state: StudioState) -> list[Send]:
    """Fan-out to all three risk agents in parallel."""
    return [
        Send("technical_auditor",    state),
        Send("compliance_agent",     state),
        Send("reputation_guardian",  state),
    ]


def route_after_risks(state: StudioState) -> Literal["luigi_escalate", "stacy_qa"]:
    return "luigi_escalate" if state.get("escalate_to_luigi") else "stacy_qa"


def route_after_qa(state: StudioState) -> str:
    if state.get("qa_passed"):
        return "marco_invoice"
    if state.get("qa_iteration", 0) >= 3:
        return END          # max retries exhausted
    return "chiara_implement"


def route_after_luigi(state: StudioState) -> str:
    return "gianni_scope" if state.get("luigi_decision") == "approved" else END


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_studio_graph():
    g = StateGraph(StudioState)

    # Register nodes
    g.add_node("stacy_classify",      stacy_classify)
    g.add_node("gianni_scope",        gianni_scope)
    g.add_node("chiara_implement",    chiara_implement)
    g.add_node("technical_auditor",   technical_auditor)
    g.add_node("compliance_agent",    compliance_agent)
    g.add_node("reputation_guardian", reputation_guardian)
    g.add_node("risk_aggregator",     risk_aggregator)
    g.add_node("stacy_qa",            stacy_qa)
    g.add_node("marco_invoice",       marco_invoice)
    g.add_node("francesca_deliver",   francesca_deliver)
    g.add_node("luigi_escalate",      luigi_escalate)

    # Entry
    g.add_edge(START, "stacy_classify")

    # stacy → Luigi (unknown) | Gianni (known)
    g.add_conditional_edges("stacy_classify", route_after_classify)

    # Gianni → Chiara
    g.add_edge("gianni_scope", "chiara_implement")

    # Chiara → parallel risk fan-out via Send
    g.add_conditional_edges("chiara_implement", dispatch_risk_agents)

    # Risk agents → aggregator (all three converge here)
    g.add_edge("technical_auditor",   "risk_aggregator")
    g.add_edge("compliance_agent",    "risk_aggregator")
    g.add_edge("reputation_guardian", "risk_aggregator")

    # Aggregator → Luigi (high risk) | QA (ok)
    g.add_conditional_edges("risk_aggregator", route_after_risks)

    # QA → invoice (pass) | retry (fail) | END (max retries)
    g.add_conditional_edges("stacy_qa", route_after_qa)

    # Marco → Francesca → END
    g.add_edge("marco_invoice",    "francesca_deliver")
    g.add_edge("francesca_deliver", END)

    # Luigi → Gianni (approved) | END (rejected)
    g.add_conditional_edges("luigi_escalate", route_after_luigi)

    return g.compile()


studio_graph = build_studio_graph()

# ── Helper for Streamlit streaming ────────────────────────────────────────────

def run_pipeline(request: str, user_name: str = "Cliente", user_email: str | None = None, config: dict | None = None) -> list[dict]:
    """Stream the pipeline and return a list of step dicts for the UI."""
    from .state import PRICING_TABLE

    initial: StudioState = {
        "request":            request,
        "user_name":          user_name,
        "user_email":         user_email,
        "input_type":         "text",
        "intent":             None,
        "product_type":       None,
        "dependencies_ok":    True,
        "technical_spec":     None,
        "stack":              None,
        "deployment_target":  None,
        "estimated_hours":    None,
        "blockers":           None,
        "deliverable_content": None,
        "deliverable_path":   None,
        "skills_used":        None,
        "qa_iteration":       0,
        "risk_reports":       [],
        "risk_passed":        True,
        "aggregate_risk_score": 0.0,
        "qa_result":          None,
        "qa_passed":          False,
        "product_price":      None,
        "invoice":            None,
        "invoice_id":         None,
        "delivery_result":    None,
        "audit_log_path":     None,
        "escalate_to_luigi":  False,
        "luigi_decision":     None,
        "escalation_reason":  None,
        "messages":           [],
        "error":              None,
        "finished":           False,
    }

    steps: list[dict] = []
    final_state = None

    for event in studio_graph.stream(initial, config=config or {}, stream_mode="values"):
        msgs = event.get("messages", [])
        if msgs:
            last = msgs[-1]
            steps.append({"content": last.content, "state_snapshot": event})
        final_state = event

    return steps, final_state
