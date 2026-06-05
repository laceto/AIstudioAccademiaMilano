"""
Avvocato AI — LangGraph StateGraph.

Pipeline:
  START → intake_agent
            └─► legal_researcher
                  └─► document_drafter
                        └─► [Send: legal_qa, compliance_check]  (parallel)
                              └─► qa_merge
                                    └─► billing_agent
                                          └─► delivery_agent
                                                └─► END
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .nodes import (
    billing_agent,
    compliance_check,
    delivery_agent,
    document_drafter,
    intake_agent,
    legal_qa,
    legal_researcher,
    qa_merge,
)
from .state import LawyerState


# ── Routing ────────────────────────────────────────────────────────────────────

def dispatch_qa_agents(state: LawyerState) -> list[Send]:
    """Fan-out: run legal_qa and compliance_check in parallel."""
    return [
        Send("legal_qa",          state),
        Send("compliance_check",  state),
    ]


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_lawyer_graph():
    g = StateGraph(LawyerState)

    g.add_node("intake_agent",      intake_agent)
    g.add_node("legal_researcher",  legal_researcher)
    g.add_node("document_drafter",  document_drafter)
    g.add_node("legal_qa",          legal_qa)
    g.add_node("compliance_check",  compliance_check)
    g.add_node("qa_merge",          qa_merge)
    g.add_node("billing_agent",     billing_agent)
    g.add_node("delivery_agent",    delivery_agent)

    # Linear backbone
    g.add_edge(START,             "intake_agent")
    g.add_edge("intake_agent",    "legal_researcher")
    g.add_edge("legal_researcher", "document_drafter")

    # After drafting → parallel QA fan-out via Send
    g.add_conditional_edges("document_drafter", dispatch_qa_agents)

    # Both QA agents converge on qa_merge
    g.add_edge("legal_qa",        "qa_merge")
    g.add_edge("compliance_check", "qa_merge")

    # QA → billing → delivery → END
    g.add_edge("qa_merge",        "billing_agent")
    g.add_edge("billing_agent",   "delivery_agent")
    g.add_edge("delivery_agent",  END)

    return g.compile(checkpointer=MemorySaver())


lawyer_graph = build_lawyer_graph()


# ── Helper ────────────────────────────────────────────────────────────────────

def run_case(
    client_request: str,
    client_name: str = "Cliente",
    contact_method: str = "email",
    config: dict | None = None,
) -> tuple[list[dict], dict]:
    """Stream the lawyer pipeline and return (steps, final_state)."""
    initial: LawyerState = {
        "client_request":      client_request,
        "client_name":         client_name,
        "contact_method":      contact_method,
        "matter_type":         None,
        "urgency":             None,
        "jurisdiction":        None,
        "intake_summary":      None,
        "legal_research":      None,
        "relevant_articles":   None,
        "relevant_cases":      None,
        "research_confidence": None,
        "draft_document":      None,
        "document_type":       None,
        "disclaimer_included": False,
        "review_reports":      [],
        "qa_passed":           False,
        "qa_issues":           None,
        "billing_type":        None,
        "hourly_rate":         None,
        "estimated_hours":     None,
        "total_fee":           None,
        "invoice":             None,
        "delivery_result":     None,
        "messages":            [],
        "error":               None,
        "finished":            False,
    }

    steps: list[dict] = []
    final_state = None

    for event in lawyer_graph.stream(initial, config=config or {}, stream_mode="values"):
        msgs = event.get("messages", [])
        if msgs:
            last = msgs[-1]
            steps.append({"content": last.content, "state_snapshot": event})
        final_state = event

    return steps, final_state
