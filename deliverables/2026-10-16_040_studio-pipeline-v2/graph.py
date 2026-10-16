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

from studio_pipeline.graph import route_after_classify, route_after_qa, run_pipeline  # noqa: F401

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

    g.add_node("lorenzo_scan",              lorenzo_scan)
    g.add_node("stacy_classify",            stacy_classify)
    g.add_node("gianni_scope",              gianni_scope)
    g.add_node("devils_advocate",           devils_advocate)
    g.add_node("financial_controller",      financial_controller)
    g.add_node("it_staff_advise",           it_staff_advise)
    g.add_node("pricing_gate",              pricing_gate)
    g.add_node("chiara_implement",          chiara_implement)
    g.add_node("technical_auditor",         technical_auditor)
    g.add_node("compliance_agent",          compliance_agent)
    g.add_node("reputation_guardian",       reputation_guardian)
    g.add_node("quality_reliability_lead",  quality_reliability_lead)
    g.add_node("api_product_designer",      api_product_designer)
    g.add_node("operational_monitor",       operational_monitor)
    g.add_node("risk_aggregator",           risk_aggregator)
    g.add_node("core_architect",            core_architect)
    g.add_node("stacy_qa",                  stacy_qa)
    g.add_node("marco_invoice",             marco_invoice)
    g.add_node("francesca_deliver",         deliver)
    g.add_node("valentina_draft",           valentina_draft)
    g.add_node("luigi_escalate",            luigi_escalate)

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
