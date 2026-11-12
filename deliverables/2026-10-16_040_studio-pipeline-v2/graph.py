"""
AI Studio Accademia Milano — pipeline v2: every role takes part.

  START → lorenzo_scan ──(injection / scan failed)──► END
            └─► stacy_classify ─(unknown)─► luigi_escalate
                  └─► gianni_scope
                        └─► [Send: devils_advocate, financial_controller, (it_staff_advise if remote deploy)]
                              └─► pricing_gate ─(vetoed, unpriced)─► luigi_escalate
                                    └─► chiara_implement
                                          └─► [Send: technical_auditor, compliance_agent, reputation_guardian,
                                                     quality_reliability_lead, api_product_designer, operational_monitor]
                                                └─► risk_aggregator
                                                      ├─(high/critical)─► luigi_escalate
                                                      ├─(triggers)──────► core_architect ─► stacy_qa
                                                      └─(ok)────────────► stacy_qa
                                                              ├─(pass)──► marco_invoice ─► francesca_deliver ─► valentina_draft ─► END
                                                              ├─(fail, retry < 3) ─► chiara_implement
                                                              └─(fail, max)       ─► END

Same HITL contract as v1: interrupt_before=["luigi_escalate"], resumed by run_pipeline().
"""
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from studio_pipeline.graph import route_after_classify as _v1_route_after_classify
from studio_pipeline.graph import route_after_qa as _v1_route_after_qa
from studio_pipeline.graph import run_pipeline  # noqa: F401  (v1's runner drives any compiled graph)

from .nodes import (
    api_product_designer,
    chiara_implement,
    compliance_agent,
    core_architect,
    devils_advocate,
    dispatch_prebuild,
    financial_controller,
    francesca_deliver,
    gianni_scope,
    it_staff_advise,
    lorenzo_scan,
    luigi_escalate,
    marco_invoice,
    operational_monitor,
    pricing_gate,
    quality_reliability_lead,
    reputation_guardian,
    risk_aggregator,
    should_consult_architect,
    stacy_classify,
    stacy_qa,
    technical_auditor,
    valentina_draft,
)
from .state import StudioStateV2

_REVIEWERS = (
    "technical_auditor", "compliance_agent", "reputation_guardian",
    "quality_reliability_lead", "api_product_designer", "operational_monitor",
)


# ── Routing functions ──────────────────────────────────────────────────────────

# v1's routers are annotated with v1's state type, which LangGraph would read as a second, clashing schema:
# the same logic, annotated with v2's.
def route_after_classify(state: StudioStateV2):
    return _v1_route_after_classify(state)


def route_after_qa(state: StudioStateV2):
    return _v1_route_after_qa(state)


def route_after_lorenzo(state: StudioStateV2) -> Literal["stacy_classify", "__end__"]:
    return END if state.get("error") or state.get("finished") else "stacy_classify"


def route_after_gate(state: StudioStateV2) -> Literal["luigi_escalate", "chiara_implement"]:
    return "luigi_escalate" if state.get("escalate_to_luigi") else "chiara_implement"


def dispatch_reviewers(state: StudioStateV2) -> list[Send]:
    return [Send(name, state) for name in _REVIEWERS]


def route_after_risks(state: StudioStateV2) -> Literal["luigi_escalate", "core_architect", "stacy_qa"]:
    if state.get("escalate_to_luigi"):
        return "luigi_escalate"
    return "core_architect" if should_consult_architect(state) else "stacy_qa"


def route_after_deliver(state: StudioStateV2) -> Literal["valentina_draft", "__end__"]:
    return "valentina_draft" if (state.get("delivery_result") or {}).get("status") in ("ready", "delivered") else END


def route_after_luigi(state: StudioStateV2) -> str:
    if state.get("luigi_decision") != "approved":
        return END
    # Where the run stopped decides where it continues: with a deliverable, QA; with a spec (the price gate
    # asked), the build; with neither (unknown product, or nothing scoped yet), the scoping.
    if (state.get("deliverable_content") or "").strip():
        return "stacy_qa"
    if state.get("technical_spec"):
        return "chiara_implement"
    return "gianni_scope"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_studio_graph(deliver=francesca_deliver, checkpointer=None, interrupt_before=("luigi_escalate",)):
    """Assemble v2. `deliver` replaces Francesca exactly as in v1 (the gateway swaps in a side-effect-free one)."""
    g = StateGraph(StudioStateV2)

    def add(name, fn):
        # v1's nodes are annotated with v1's StudioState, whose risk_reports reducer differs from v2's;
        # without an explicit input schema LangGraph reads that hint and rejects the clash.
        g.add_node(name, fn, input_schema=StudioStateV2)

    add("lorenzo_scan", lorenzo_scan)
    add("stacy_classify", stacy_classify)
    add("gianni_scope", gianni_scope)
    add("devils_advocate", devils_advocate)
    add("financial_controller", financial_controller)
    add("it_staff_advise", it_staff_advise)
    add("pricing_gate", pricing_gate)
    add("chiara_implement", chiara_implement)
    add("technical_auditor", technical_auditor)
    add("compliance_agent", compliance_agent)
    add("reputation_guardian", reputation_guardian)
    add("quality_reliability_lead", quality_reliability_lead)
    add("api_product_designer", api_product_designer)
    add("operational_monitor", operational_monitor)
    add("risk_aggregator", risk_aggregator)
    add("core_architect", core_architect)
    add("stacy_qa", stacy_qa)
    add("marco_invoice", marco_invoice)
    add("francesca_deliver", deliver)
    add("valentina_draft", valentina_draft)
    add("luigi_escalate", luigi_escalate)

    g.add_edge(START, "lorenzo_scan")
    g.add_conditional_edges("lorenzo_scan", route_after_lorenzo)
    g.add_conditional_edges("stacy_classify", route_after_classify)

    g.add_conditional_edges("gianni_scope", dispatch_prebuild)
    for name in ("devils_advocate", "financial_controller", "it_staff_advise"):
        g.add_edge(name, "pricing_gate")
    g.add_conditional_edges("pricing_gate", route_after_gate)

    g.add_conditional_edges("chiara_implement", dispatch_reviewers)
    for name in _REVIEWERS:
        g.add_edge(name, "risk_aggregator")
    g.add_conditional_edges("risk_aggregator", route_after_risks)
    g.add_edge("core_architect", "stacy_qa")

    g.add_conditional_edges("stacy_qa", route_after_qa)
    g.add_edge("marco_invoice", "francesca_deliver")
    g.add_conditional_edges("francesca_deliver", route_after_deliver)
    g.add_edge("valentina_draft", END)
    g.add_conditional_edges("luigi_escalate", route_after_luigi)

    return g.compile(checkpointer=checkpointer or MemorySaver(), interrupt_before=list(interrupt_before))


studio_graph = build_studio_graph()
