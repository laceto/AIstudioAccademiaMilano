"""
Studio Digital Twin — LangGraph assembly.

Graph topology:
  START → load_state → dispatch_departments
                         ↓ (parallel Send to 5 nodes)
           stacy_sim | gianni_sim | chiara_sim | marco_sim | francesca_sim
                         ↓ (all converge at synthesizer via operator.add)
                      synthesizer → END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .nodes import (
    chiara_sim,
    francesca_sim,
    gianni_sim,
    marco_sim,
    stacy_sim,
    synthesizer,
)
from .state import TwinState
from .studio_loader import load_studio_state_node

_DEPARTMENTS = ["stacy_sim", "gianni_sim", "chiara_sim", "marco_sim", "francesca_sim"]


def _dispatch_departments(state: TwinState) -> list[Send]:
    return [Send(dept, state) for dept in _DEPARTMENTS]


def build_twin_graph():
    g = StateGraph(TwinState)

    g.add_node("load_state",    load_studio_state_node)
    g.add_node("stacy_sim",     stacy_sim)
    g.add_node("gianni_sim",    gianni_sim)
    g.add_node("chiara_sim",    chiara_sim)
    g.add_node("marco_sim",     marco_sim)
    g.add_node("francesca_sim", francesca_sim)
    g.add_node("synthesizer",   synthesizer)

    g.add_edge(START, "load_state")
    g.add_conditional_edges("load_state", _dispatch_departments)

    for dept in _DEPARTMENTS:
        g.add_edge(dept, "synthesizer")

    g.add_edge("synthesizer", END)

    return g.compile()


twin_graph = build_twin_graph()


def run_simulation(
    event: dict,
    studio_baseline: dict | None = None,
    config: dict | None = None,
) -> tuple[list[dict], dict]:
    """
    Run a simulation and return (steps, final_state).

    steps: list of intermediate state snapshots (one per graph event)
    final_state: the complete TwinState after the graph finishes
    """
    from studio_loader import load_studio_baseline

    initial: TwinState = {
        "event":              event,
        "studio_baseline":    studio_baseline or load_studio_baseline(),
        "department_impacts": [],
        "simulation_report":  None,
        "messages":           [],
        "error":              None,
        "finished":           False,
    }

    steps: list[dict] = []
    final_state: dict = {}

    for chunk in twin_graph.stream(initial, config=config or {}, stream_mode="updates"):
        steps.append(chunk)
        final_state = chunk

    return steps, final_state
