"""
Reinsurance Branch Office — LangGraph node functions.

Five roles:
  branch_manager          fast  — intake, routing, final approval (HITL)
  medical_underwriter     smart — medical risk & claim validity
  actuarial_analyst       smart — loss ratios, IBNR, pricing adequacy
  accountant              fast  — bordereaux entries, reserve movements
  sr_accounting_exec      smart — consolidated P&L, regulatory flags, sign-off
"""
import json
import uuid
from datetime import datetime

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .llm_factory import get_llm
from .state import BranchState


def _provider(config: RunnableConfig) -> str:
    return (config or {}).get("configurable", {}).get("provider", "anthropic")


# ── Branch Manager: Intake ─────────────────────────────────────────────────────

def branch_manager_intake(state: BranchState, config: RunnableConfig) -> dict:
    try:
        llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Principal Officer / Branch Manager of a reinsurance branch office.
Your job: receive a case submission and produce a structured intake summary.
Return ONLY valid JSON:
{{
  "intake_summary": "one paragraph summarising the case, workflow type and key facts",
  "case_status": "open",
  "routing_notes": "which specialists need to review this"
}}
Workflow types: claim (incoming claim to process), treaty (new treaty to evaluate), report (monthly reporting cycle)."""),
            ("human", "Workflow: {workflow_type}\nCase ID: {case_id}\nSubmission:\n{case_input}"),
        ])

        result = (prompt | llm | JsonOutputParser()).invoke({
            "workflow_type": state["workflow_type"],
            "case_id": state["case_id"],
            "case_input": state["case_input"],
        })

        return {
            "intake_summary": result.get("intake_summary", ""),
            "case_status": result.get("case_status", "open"),
            "messages": [AIMessage(content=f"[Branch Manager] Intake complete. {result.get('routing_notes', '')}")],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "messages": [AIMessage(content=f"[Branch Manager Intake] ERROR: {exc}")],
        }


# ── Medical Underwriter / Claim Analyst ───────────────────────────────────────

def medical_underwriter(state: BranchState, config: RunnableConfig) -> dict:
    try:
        llm = get_llm(_provider(config), "smart", max_tokens=2048, temperature=0.1)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Medical Underwriter and Claim Analyst of a reinsurance branch office.
For claims: assess medical validity, diagnosis flags, reserve recommendation.
For treaties: assess the medical risk profile of the covered portfolio.
Return ONLY valid JSON:
{{
  "risk_level": "low|medium|high",
  "diagnosis_flags": ["list of flags or empty"],
  "claim_validity": "valid|invalid|requires_more_info",
  "recommended_reserve": "amount in EUR as string, e.g. 15000",
  "notes": "professional assessment in 2-3 sentences"
}}"""),
            ("human", "Workflow: {workflow_type}\nIntake summary: {intake_summary}\nOriginal submission: {case_input}"),
        ])

        result = (prompt | llm | JsonOutputParser()).invoke({
            "workflow_type": state["workflow_type"],
            "intake_summary": state.get("intake_summary", ""),
            "case_input": state["case_input"],
        })

        return {
            "medical_assessment": result,
            "parallel_reports": [{"role": "medical_underwriter", "data": result}],
            "messages": [AIMessage(content=(
                f"[Medical Underwriter] Risk: {result.get('risk_level')} | "
                f"Validity: {result.get('claim_validity')} | "
                f"Reserve: €{result.get('recommended_reserve', 'TBD')}"
            ))],
        }
    except Exception as exc:
        return {
            "parallel_reports": [{"role": "medical_underwriter", "error": str(exc)}],
            "error": str(exc),
            "messages": [AIMessage(content=f"[Medical Underwriter] ERROR: {exc}")],
        }


# ── Actuarial Analyst ──────────────────────────────────────────────────────────

def actuarial_analyst(state: BranchState, config: RunnableConfig) -> dict:
    try:
        llm = get_llm(_provider(config), "smart", max_tokens=2048, temperature=0.1)

        medical = state.get("medical_assessment") or {}
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Actuarial Analyst of a reinsurance branch office.
Actuarial background: apply P(event) × impact × blast_radius → Risk Units (RU).
For claims: calculate loss ratio impact, IBNR adjustment, pricing adequacy.
For treaties: price the risk, define retention/cession levels, flag if adequacy < 0.85.
For reports: compute period loss ratios, reserve development, trend analysis.
Return ONLY valid JSON:
{{
  "loss_ratio": "as decimal string e.g. 0.72",
  "ibnr_reserve": "EUR amount string",
  "pricing_adequacy": "decimal string e.g. 0.91",
  "risk_units": "float string e.g. 2.4",
  "flag_p1": false,
  "notes": "actuarial assessment in 2-3 sentences"
}}"""),
            ("human", "Workflow: {workflow_type}\nMedical assessment: {medical}\nCase: {case_input}"),
        ])

        result = (prompt | llm | JsonOutputParser()).invoke({
            "workflow_type": state["workflow_type"],
            "medical": json.dumps(medical),
            "case_input": state["case_input"],
        })

        return {
            "actuarial_assessment": result,
            "parallel_reports": [{"role": "actuarial_analyst", "data": result}],
            "messages": [AIMessage(content=(
                f"[Actuarial Analyst] Loss ratio: {result.get('loss_ratio')} | "
                f"RU: {result.get('risk_units')} | "
                f"Adequacy: {result.get('pricing_adequacy')}"
                + (" ⚠ P1 FLAG" if result.get("flag_p1") else "")
            ))],
        }
    except Exception as exc:
        return {
            "parallel_reports": [{"role": "actuarial_analyst", "error": str(exc)}],
            "error": str(exc),
            "messages": [AIMessage(content=f"[Actuarial Analyst] ERROR: {exc}")],
        }


# ── Parallel aggregator (treaty / report fan-out convergence) ─────────────────

def parallel_aggregator(state: BranchState, config: RunnableConfig) -> dict:
    try:
        reports = state.get("parallel_reports", [])
        medical = next((r["data"] for r in reports if r.get("role") == "medical_underwriter" and "data" in r), None)
        actuarial = next((r["data"] for r in reports if r.get("role") == "actuarial_analyst" and "data" in r), None)

        return {
            "medical_assessment": medical or state.get("medical_assessment"),
            "actuarial_assessment": actuarial or state.get("actuarial_assessment"),
            "messages": [AIMessage(content=f"[Aggregator] Parallel reviews merged. Reports received: {[r['role'] for r in reports]}")],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "messages": [AIMessage(content=f"[Aggregator] ERROR: {exc}")],
        }


# ── Accountant ────────────────────────────────────────────────────────────────

def accountant(state: BranchState, config: RunnableConfig) -> dict:
    try:
        llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

        medical = state.get("medical_assessment") or {}
        actuarial = state.get("actuarial_assessment") or {}

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Accountant of a reinsurance branch office.
Process the bordereaux entries and reserve movements based on the specialist reviews.
Return ONLY valid JSON:
{{
  "debit_account": "account name",
  "credit_account": "account name",
  "reserve_movement": "EUR amount with sign e.g. +15000 or -3000",
  "net_impact": "EUR amount with sign",
  "currency": "EUR",
  "entry_type": "claim_payment|reserve_increase|premium_booking|treaty_entry",
  "notes": "one sentence"
}}"""),
            ("human", "Workflow: {workflow_type}\nMedical: {medical}\nActuarial: {actuarial}"),
        ])

        result = (prompt | llm | JsonOutputParser()).invoke({
            "workflow_type": state["workflow_type"],
            "medical": json.dumps(medical),
            "actuarial": json.dumps(actuarial),
        })

        return {
            "accounting_entries": result,
            "messages": [AIMessage(content=(
                f"[Accountant] Entry: {result.get('entry_type')} | "
                f"Reserve: {result.get('reserve_movement')} | "
                f"Net: {result.get('net_impact')} {result.get('currency', 'EUR')}"
            ))],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "messages": [AIMessage(content=f"[Accountant] ERROR: {exc}")],
        }


# ── Sr Accounting Executive ────────────────────────────────────────────────────

def sr_accounting_exec(state: BranchState, config: RunnableConfig) -> dict:
    try:
        llm = get_llm(_provider(config), "smart", max_tokens=2048, temperature=0.1)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Senior Accounting Executive of a reinsurance branch office.
Consolidate all specialist inputs into a P&L report and regulatory sign-off assessment.
Return ONLY valid JSON:
{{
  "summary": "executive summary in 3-4 sentences",
  "pl_impact": "EUR amount with sign",
  "regulatory_flags": ["list or empty"],
  "sign_off_ready": true,
  "recommended_action": "approve|reject|request_more_info",
  "notes": "any caveats or conditions"
}}"""),
            ("human", "Workflow: {workflow_type}\nMedical: {medical}\nActuarial: {actuarial}\nAccounting: {accounting}"),
        ])

        result = (prompt | llm | JsonOutputParser()).invoke({
            "workflow_type": state["workflow_type"],
            "medical": json.dumps(state.get("medical_assessment") or {}),
            "actuarial": json.dumps(state.get("actuarial_assessment") or {}),
            "accounting": json.dumps(state.get("accounting_entries") or {}),
        })

        return {
            "financial_report": result,
            "awaiting_approval": True,
            "approval_requested_from": "branch_manager",
            "messages": [AIMessage(content=(
                f"[Sr Accounting Exec] P&L impact: {result.get('pl_impact')} | "
                f"Sign-off ready: {result.get('sign_off_ready')} | "
                f"Recommendation: {result.get('recommended_action')}"
            ))],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "messages": [AIMessage(content=f"[Sr Accounting Exec] ERROR: {exc}")],
        }


# ── Branch Manager: Final Approval (Human-in-the-Loop gate) ───────────────────

def branch_manager_approve(state: BranchState, config: RunnableConfig) -> dict:
    """
    HITL node — in production this interrupts and waits for a human decision.
    When resumed, state["manager_decision"] is set externally (approved|rejected).
    For demo/auto mode: auto-approve if sign_off_ready and no regulatory flags.
    """
    try:
        report = state.get("financial_report") or {}
        auto_mode = (config or {}).get("configurable", {}).get("auto_approve", True)

        if auto_mode:
            flags = report.get("regulatory_flags", [])
            recommendation = report.get("recommended_action", "approve")
            decision = "approved" if (recommendation == "approve" and not flags) else "rejected"
        else:
            decision = state.get("manager_decision", "pending")

        status = "approved" if decision == "approved" else (
            "rejected" if decision == "rejected" else "pending_info"
        )

        summary = report.get("summary", "")
        final = (
            f"CASE {state['case_id']} — {status.upper()}\n\n"
            f"{summary}\n\n"
            f"P&L Impact: {report.get('pl_impact', 'N/A')}\n"
            f"Regulatory flags: {', '.join(report.get('regulatory_flags', [])) or 'None'}\n"
            f"Decision: {decision.upper()}\n"
            f"Signed: Branch Manager — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        return {
            "manager_decision": decision,
            "case_status": status,
            "awaiting_approval": False,
            "final_output": final,
            "finished": True,
            "messages": [AIMessage(content=f"[Branch Manager] ✓ Case {state['case_id']} — {status.upper()}")],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "messages": [AIMessage(content=f"[Branch Manager Approve] ERROR: {exc}")],
        }
