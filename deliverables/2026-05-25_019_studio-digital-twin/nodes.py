"""
Studio Digital Twin — simulation nodes.

Each department node receives the injected event + studio baseline, then
simulates (via LLM) what would happen to that department. Nodes run in
parallel via LangGraph Send dispatch and accumulate into department_impacts.

The synthesizer runs after all departments and produces the final report.
"""
from __future__ import annotations

import json
from datetime import datetime

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .llm_factory import get_llm
from .state import TwinState


def _provider(config: RunnableConfig) -> str:
    return (config or {}).get("configurable", {}).get("provider", "anthropic")


_DEPT_SYSTEM = """\
You are simulating the {department} agent of AI Studio Accademia Milano in response to an external event.

THIS IS A SIMULATION — you are modeling/predicting impact, not executing real work.

Studio baseline (current live state):
{baseline}

External event injected into the simulation:
{event}

As {department}, reason about:
1. How does this event change what you do / can do?
2. What is the operational impact (what breaks, adapts, or gets worse)?
3. What is the financial delta for this department (positive or negative EUR)?
4. What is the single most important action to take in response?
5. Which other departments are affected downstream?

Return ONLY valid JSON — no markdown, no explanation:
{{
  "department": "{department}",
  "severity": <1-5 integer>,
  "impact_summary": "<2-3 sentence summary>",
  "operational_impact": "<concrete changes to this department's operation>",
  "financial_delta_eur": <float — negative means cost/loss, positive means gain>,
  "recommended_action": "<single most important action, owner, deadline>",
  "cascading_to": ["<department>", "..."],
  "confidence": <0.0-1.0>
}}"""

_DEPT_ROLES = {
    "stacy":     "Input Orchestrator — classifies all incoming requests, enforces pricing gates, routes to Gianni",
    "gianni":    "Technical Scoper — decomposes requests into specs, selects stack, estimates hours, identifies blockers",
    "chiara":    "Implementer — builds all deliverables (code, PDFs, agents); the only node that produces billable output",
    "marco":     "Financial Controller — prices every delivery, issues invoices, blocks on unknown products; actuarial background",
    "francesca": "Delivery Agent — pushes to GitHub, deploys, sends emails, writes audit logs; final step before client handoff",
}


def _dept_node(department: str, state: TwinState, config: RunnableConfig) -> dict:
    try:
        llm = get_llm(_provider(config), "smart", max_tokens=2048, temperature=0.1)
        prompt = ChatPromptTemplate.from_messages([
            ("system", _DEPT_SYSTEM),
            ("human", "Simulate the impact on {department} ({role})."),
        ])
        chain = prompt | llm | JsonOutputParser()
        impact: dict = chain.invoke({
            "department": department,
            "role":       _DEPT_ROLES[department],
            "baseline":   json.dumps(state["studio_baseline"], indent=2),
            "event":      json.dumps(state["event"], indent=2),
        })
        impact["department"] = department
        return {
            "department_impacts": [impact],
            "messages": [AIMessage(content=(
                f"[{department}_sim] severity={impact.get('severity')}/5 | "
                f"delta=€{impact.get('financial_delta_eur', 0):.0f} | "
                f"confidence={impact.get('confidence', 0):.0%}"
            ))],
        }
    except Exception as exc:
        return {
            "department_impacts": [{"department": department, "error": str(exc)}],
            "error": str(exc),
            "messages": [AIMessage(content=f"[{department}_sim] ERROR: {exc}")],
        }


# ── five department simulation nodes ──────────────────────────────────────────

def stacy_sim(state: TwinState, config: RunnableConfig) -> dict:
    return _dept_node("stacy", state, config)

def gianni_sim(state: TwinState, config: RunnableConfig) -> dict:
    return _dept_node("gianni", state, config)

def chiara_sim(state: TwinState, config: RunnableConfig) -> dict:
    return _dept_node("chiara", state, config)

def marco_sim(state: TwinState, config: RunnableConfig) -> dict:
    return _dept_node("marco", state, config)

def francesca_sim(state: TwinState, config: RunnableConfig) -> dict:
    return _dept_node("francesca", state, config)


# ── synthesizer ───────────────────────────────────────────────────────────────

_SYNTH_SYSTEM = """\
You are the synthesis engine of a digital twin for AI Studio Accademia Milano.
All five pipeline departments have simulated their response to an external event.
Your job: aggregate their outputs into one coherent simulation report.

Studio baseline:
{baseline}

Injected event:
{event}

Department simulation outputs:
{impacts}

Produce a single JSON report. Be specific and quantitative where possible.
Return ONLY valid JSON — no markdown, no explanation:
{{
  "overall_severity": <1-5 float — weighted average across departments>,
  "narrative": "<3-5 sentence plain-language summary of what happens to the Studio>",
  "financial_impact": {{
    "revenue_delta_eur": <float>,
    "cost_delta_eur":    <float>,
    "margin_delta_pct":  <float>
  }},
  "bottlenecks": ["<department or process that becomes the limiting factor>", "..."],
  "recommended_actions": [
    {{"priority": 1, "action": "<what to do>", "owner": "<agent>", "timeline": "<immediate|24h|1week>"}},
    {{"priority": 2, "action": "...", "owner": "...", "timeline": "..."}}
  ],
  "resilience_score": <0-10 float — how well the Studio absorbs this event>,
  "time_to_recover_days": <integer estimate>,
  "upsides": ["<any positive second-order effects, if any>"],
  "disclaimer": "This is a simulation output generated by an AI digital twin. Not a prediction or professional advice."
}}"""


def synthesizer(state: TwinState, config: RunnableConfig) -> dict:
    try:
        llm = get_llm(_provider(config), "smart", max_tokens=2048, temperature=0.1)
        prompt = ChatPromptTemplate.from_messages([
            ("system", _SYNTH_SYSTEM),
            ("human", "Synthesize the simulation report now."),
        ])
        chain = prompt | llm | JsonOutputParser()
        report: dict = chain.invoke({
            "baseline": json.dumps(state["studio_baseline"], indent=2),
            "event":    json.dumps(state["event"], indent=2),
            "impacts":  json.dumps(state["department_impacts"], indent=2),
        })
        report["simulation_timestamp"] = datetime.now().isoformat()
        report["event"]                = state["event"]
        report["department_details"]   = state["department_impacts"]
        return {
            "simulation_report": report,
            "finished":          True,
            "messages": [AIMessage(content=(
                f"[Synthesizer] severity={report.get('overall_severity', '?')}/5 | "
                f"resilience={report.get('resilience_score', '?')}/10 | "
                f"recover={report.get('time_to_recover_days', '?')}d"
            ))],
        }
    except Exception as exc:
        return {
            "error":    str(exc),
            "finished": True,
            "messages": [AIMessage(content=f"[Synthesizer] ERROR: {exc}")],
        }
