"""
AI Studio LangGraph — agent node functions.

Every node accepts (state, config) — LangGraph injects config automatically.
The provider is read from config["configurable"]["provider"] (default: "anthropic").

  fast tier  → haiku-4.5  / gpt-4o-mini  (Stacy, risk agents, QA checks)
  smart tier → sonnet-4.6 / gpt-4o       (Gianni scope, Chiara implement)
"""
import json
import uuid
from datetime import datetime

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .llm_factory import get_llm
from .state import PRICING_TABLE, StudioState


def _provider(config: RunnableConfig) -> str:
    return (config or {}).get("configurable", {}).get("provider", "anthropic")


# ── Stacy Step 1: Intent Classifier ───────────────────────────────────────────
def stacy_classify(state: StudioState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are Stacy, Input-Orchestrator for AI Studio Accademia Milano.
Classify the user request and return ONLY valid JSON:
{{
  "intent": "website_creation|pdf_creation|invoice_generation|chatbot_app|rag_knowledge_base|strategic_report|calendar_integration|weather_dashboard|agent_deploy_streamlit|other",
  "product_type": "one of: static_landing_page, premium_landing_page, commercial_landing_page, pdf_document, invoice_pdf, strategic_report, chatbot_app, email_delivery, rag_knowledge_base, calendar_integration, weather_dashboard, agent_deploy_streamlit — OR unknown_product",
  "dependencies_ok": true,
  "input_type": "text"
}}"""),
        ("human", "{request}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({"request": state["request"]})

    product_type = result.get("product_type", "unknown_product")
    price = PRICING_TABLE.get(product_type)
    escalate = price is None

    return {
        "intent":            result.get("intent", "unknown"),
        "product_type":      product_type,
        "dependencies_ok":   result.get("dependencies_ok", True),
        "escalate_to_luigi": escalate,
        "escalation_reason": f"Unknown product: {product_type}" if escalate else None,
        "messages": [AIMessage(content=(
            f"[Stacy] intent={result.get('intent')} | product={product_type} | "
            f"price={'€' + price if price else 'UNKNOWN → escalate to Luigi'}"
        ))],
    }


# ── Gianni: Technical Scoper ───────────────────────────────────────────────────
def gianni_scope(state: StudioState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "smart", max_tokens=4096, temperature=0.2)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are Gianni, Request-Analyzer for AI Studio Accademia Milano.
Decompose the request into a full technical spec. Return ONLY valid JSON:
{{
  "technical_spec": {{
    "overview": "...",
    "components": ["..."],
    "api_integrations": ["..."],
    "data_model": "..."
  }},
  "stack": ["Python", "Streamlit", "..."],
  "deployment_target": "Streamlit Cloud | Vercel | GitHub | local",
  "estimated_hours": 2.5,
  "blockers": []
}}"""),
        ("human", "Request: {request}\nIntent: {intent}\nProduct: {product_type}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "request":      state["request"],
        "intent":       state.get("intent", ""),
        "product_type": state.get("product_type", ""),
    })

    return {
        "technical_spec":    result.get("technical_spec", {}),
        "stack":             result.get("stack", []),
        "deployment_target": result.get("deployment_target", "local"),
        "estimated_hours":   result.get("estimated_hours", 1.0),
        "blockers":          result.get("blockers", []),
        "messages": [AIMessage(content=(
            f"[Gianni] stack={result.get('stack')} | "
            f"deploy={result.get('deployment_target')} | "
            f"eta={result.get('estimated_hours')}h | "
            f"blockers={result.get('blockers', [])}"
        ))],
    }


# ── Chiara: Implementer ────────────────────────────────────────────────────────
def chiara_implement(state: StudioState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "smart", max_tokens=8192, temperature=0.2)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are Chiara, Product-Generator for AI Studio Accademia Milano.
Implement the deliverable exactly per the technical spec. No scope creep.
Return ONLY valid JSON:
{{
  "deliverable_content": "...full production-ready code or document...",
  "deliverable_path": "deliverables/YYYY-MM-DD_NNN_slug/main.py",
  "skills_used": ["streamlit", "openai_api", "fpdf2"]
}}"""),
        ("human", "Request: {request}\nSpec: {spec}\nStack: {stack}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "request": state["request"],
        "spec":    json.dumps(state.get("technical_spec", {}), indent=2),
        "stack":   str(state.get("stack", [])),
    })

    iteration = state.get("qa_iteration", 0)

    return {
        "deliverable_content": result.get("deliverable_content", ""),
        "deliverable_path":    result.get("deliverable_path", "deliverables/output/main.py"),
        "skills_used":         result.get("skills_used", []),
        "qa_iteration":        iteration + 1,
        "risk_reports":        [],
        "messages": [AIMessage(content=(
            f"[Chiara] built {result.get('deliverable_path')} "
            f"(attempt {iteration + 1}) | skills={result.get('skills_used')}"
        ))],
    }


# ── Risk agents (run in parallel via Send) ─────────────────────────────────────

def technical_auditor(state: StudioState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are the Technical Auditor. Scan for:
- Hardcoded secrets / API keys
- Injection vectors (SQL, command, XSS)
- Missing error handling / rollback paths

Return ONLY valid JSON: {{"risk_score": 1, "findings": [], "agent": "technical_auditor"}}
Scale: 1=safe, 5=critical."""),
        ("human", "Deliverable (first 2000 chars): {content}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke(
        {"content": (state.get("deliverable_content") or "")[:2000]}
    )
    result["agent"] = "technical_auditor"

    return {
        "risk_reports": [result],
        "messages": [AIMessage(content=f"[TechAuditor] risk={result.get('risk_score')}/5 | findings={result.get('findings')}")],
    }


def compliance_agent(state: StudioState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are the Compliance Agent. Check:
- GDPR: personal data, consent, right to erasure
- API ToS adherence
- Advisory disclaimer present?

Return ONLY valid JSON: {{"risk_score": 1, "findings": [], "agent": "compliance_agent"}}"""),
        ("human", "Deliverable: {content}\nIntent: {intent}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "content": (state.get("deliverable_content") or "")[:1500],
        "intent":  state.get("intent", ""),
    })
    result["agent"] = "compliance_agent"

    return {
        "risk_reports": [result],
        "messages": [AIMessage(content=f"[Compliance] risk={result.get('risk_score')}/5 | findings={result.get('findings')}")],
    }


def reputation_guardian(state: StudioState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are the Reputation Guardian. Assess:
- Output quality (professional standards?)
- Factual accuracy
- Brand voice alignment

Return ONLY valid JSON: {{"risk_score": 1, "findings": [], "agent": "reputation_guardian"}}"""),
        ("human", "Deliverable preview: {content}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke(
        {"content": (state.get("deliverable_content") or "")[:1000]}
    )
    result["agent"] = "reputation_guardian"

    return {
        "risk_reports": [result],
        "messages": [AIMessage(content=f"[Reputation] risk={result.get('risk_score')}/5 | findings={result.get('findings')}")],
    }


# ── Risk Aggregator ────────────────────────────────────────────────────────────
def risk_aggregator(state: StudioState) -> dict:
    reports = state.get("risk_reports", [])
    if not reports:
        return {
            "risk_passed": True, "aggregate_risk_score": 1.0,
            "messages": [AIMessage(content="[RiskPanel] No reports — defaulting safe.")],
        }

    scores    = [r.get("risk_score", 1) for r in reports]
    aggregate = sum(scores) / len(scores)
    passed    = aggregate < 3.5

    return {
        "aggregate_risk_score": aggregate,
        "risk_passed":          passed,
        "escalate_to_luigi":    not passed,
        "escalation_reason":    f"Aggregate risk {aggregate:.1f}/5 exceeds 2σ" if not passed else None,
        "messages": [AIMessage(content=(
            f"[RiskPanel] scores={scores} avg={aggregate:.1f}/5 → "
            f"{'PASS' if passed else 'FAIL — escalating to Luigi'}"
        ))],
    }


# ── Stacy QA ───────────────────────────────────────────────────────────────────
def stacy_qa(state: StudioState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are Stacy in QA mode. Validate:
1. Format matches technical spec
2. No hardcoded secrets
3. Disclaimer present if advisory content
4. All required components present

Return ONLY valid JSON:
{{
  "qa_passed": true,
  "checks": {{"format": true, "security": true, "disclaimer": true, "completeness": true}},
  "issues": []
}}"""),
        ("human", "Spec: {spec}\nDeliverable (first 2000 chars): {content}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "spec":    json.dumps(state.get("technical_spec", {})),
        "content": (state.get("deliverable_content") or "")[:2000],
    })

    return {
        "qa_result": result,
        "qa_passed": result.get("qa_passed", False),
        "messages": [AIMessage(content=(
            f"[Stacy QA] {'PASS' if result.get('qa_passed') else 'FAIL: ' + str(result.get('issues', []))}"
        ))],
    }


# ── Marco: Finance ─────────────────────────────────────────────────────────────
def marco_invoice(state: StudioState) -> dict:
    product_type = state.get("product_type", "unknown_product")
    price        = PRICING_TABLE.get(product_type)

    if price is None:
        return {
            "escalate_to_luigi":  True,
            "escalation_reason":  f"Marco blocked — cannot price: {product_type}",
            "messages": [AIMessage(content=f"[Marco] BLOCKED — unknown product: {product_type}")],
        }

    invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    invoice = {
        "invoice_id":  invoice_id,
        "product":     product_type,
        "price_eur":   float(price),
        "date":        datetime.now().isoformat(),
        "client":      state.get("user_name", "Cliente"),
        "status":      "issued",
    }

    return {
        "product_price": price,
        "invoice":       invoice,
        "invoice_id":    invoice_id,
        "messages": [AIMessage(content=f"[Marco] Invoice {invoice_id}: €{price} — {product_type}")],
    }


# ── Francesca: Delivery ────────────────────────────────────────────────────────

def _next_audit_id(audit_dir) -> int:
    import re
    from pathlib import Path
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_(\d+)_")
    ids = [
        int(m.group(1))
        for f in Path(audit_dir).iterdir()
        if (m := pattern.match(f.name))
    ]
    return (max(ids) + 1) if ids else 1


def _write_audit_log(path, state: StudioState, req_id: int, datestr: str, deliverable_path: str) -> None:
    from pathlib import Path

    agents = [
        {"name": "Stacy",     "role": "input_orchestrator",  "status": "success"},
        {"name": "Gianni",    "role": "request_analyzer",    "status": "success"},
        {"name": "Chiara",    "role": "product_generator",   "status": "success"},
        {"name": "TechAudit", "role": "technical_auditor",   "status": "success"},
        {"name": "Compliance","role": "compliance_agent",    "status": "success"},
        {"name": "Reputation","role": "reputation_guardian", "status": "success"},
        {"name": "Stacy",     "role": "qa_agent",            "status": "success"},
        {"name": "Marco",     "role": "transaction_manager", "status": "success"},
        {"name": "Francesca", "role": "delivery_agent",      "status": "success"},
    ]
    agents_yaml = "\n".join(
        f'  - name: {a["name"]}\n    role: {a["role"]}\n    status: {a["status"]}'
        for a in agents
    )
    skills = state.get("skills_used") or []
    skills_yaml = "\n".join(f"  - {s}" for s in skills) or "  []"

    invoice = state.get("invoice") or {}
    risk_score = int(state.get("aggregate_risk_score", 1))

    content = f"""# Audit Log — Request {req_id:03d}

```yaml
request_id: "{req_id:03d}"
date: "{datestr}"
input_type: {state.get("input_type", "text")}
raw_input: |
  {state.get("request", "").strip()}
intent: {state.get("intent", "unknown")}
product_type: {state.get("product_type", "unknown")}

agents_invoked:
{agents_yaml}

skills_used:
{skills_yaml}

qa_result: {"pass" if state.get("qa_passed") else "fail"}
qa_iterations: {state.get("qa_iteration", 1)}

payment:
  amount: "€{state.get("product_price", "0.00")}"
  invoice_id: {state.get("invoice_id", "N/A")}
  status: {invoice.get("status", "issued")}

delivery:
  deliverable_path: {deliverable_path}

outcome: success

learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: {max(1, risk_score)}
```
"""
    Path(path).write_text(content, encoding="utf-8")


def _git_commit_and_push(root, files: list[str], slug: str) -> str:
    import subprocess
    try:
        subprocess.run(
            ["git", "add"] + files,
            cwd=str(root), capture_output=True, check=True,
        )
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(root), capture_output=True, text=True,
        ).stdout.strip() or "main"
        subprocess.run(
            ["git", "commit", "-m", f"deliver: {slug}"],
            cwd=str(root), capture_output=True, check=True,
        )
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=str(root), capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return f"pushed to {branch}"
        return f"push failed: {result.stderr.strip()[:120]}"
    except subprocess.CalledProcessError as e:
        return f"git error: {(e.stderr or b'').decode()[:120]}"
    except Exception as e:
        return f"error: {e}"


def _send_email(state: StudioState, slug: str, deliverable_path) -> str:
    import os
    import smtplib
    from email.mime.text import MIMEText

    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    recipient  = state.get("user_email") or gmail_user
    if not (gmail_user and gmail_pass and recipient):
        return "skipped (no credentials)"

    body = (
        f"Ciao {state.get('user_name', 'Cliente')},\n\n"
        f"Il tuo deliverable è pronto: {slug}\n"
        f"File: {deliverable_path}\n"
        f"Invoice: {state.get('invoice_id', 'N/A')} — €{state.get('product_price', '0.00')}\n\n"
        "— AI Studio Accademia Milano"
    )
    msg = MIMEText(body)
    msg["Subject"] = f"[AI Studio] Consegna: {slug}"
    msg["From"]    = gmail_user
    msg["To"]      = recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, [recipient], msg.as_string())
        return f"sent to {recipient}"
    except Exception as e:
        return f"email error: {e}"


def francesca_deliver(state: StudioState) -> dict:
    import subprocess
    from pathlib import Path

    ROOT      = Path(__file__).resolve().parent.parent.parent
    AUDIT_DIR = ROOT / "process" / "audit"
    datestr   = datetime.now().strftime("%Y-%m-%d")

    # 1. Resolve next audit ID and slug
    next_id      = _next_audit_id(AUDIT_DIR)
    product_slug = (state.get("product_type") or "output").replace("_", "-")
    slug         = f"{datestr}_{next_id:03d}_{product_slug}"

    # 2. Write deliverable to disk
    raw_path        = state.get("deliverable_path") or "deliverables/output/main.py"
    filename        = Path(raw_path).name or "main.py"
    deliverable_dir = ROOT / "deliverables" / slug
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    actual_path = deliverable_dir / filename
    actual_path.write_text(state.get("deliverable_content") or "", encoding="utf-8")

    rel_deliverable = str(actual_path.relative_to(ROOT))

    # 3. Write audit log
    audit_log_path = AUDIT_DIR / f"{slug}.md"
    _write_audit_log(audit_log_path, state, next_id, datestr, rel_deliverable)
    rel_audit = str(audit_log_path.relative_to(ROOT))

    # 4. Git commit + push
    git_status = _git_commit_and_push(
        ROOT,
        [str(actual_path), str(audit_log_path)],
        slug,
    )

    # 5. Trigger post_delivery_update.py (non-fatal)
    try:
        subprocess.run(
            ["python", "scripts/post_delivery_update.py"],
            cwd=str(ROOT), capture_output=True, timeout=30,
        )
    except Exception:
        pass

    # 6. Best-effort email
    email_status = _send_email(state, slug, rel_deliverable)

    result = {
        "deliverable_path": rel_deliverable,
        "audit_log":        rel_audit,
        "git_status":       git_status,
        "email_status":     email_status,
        "status":           "delivered",
    }

    return {
        "delivery_result": result,
        "audit_log_path":  rel_audit,
        "finished":        True,
        "messages": [AIMessage(content=(
            f"[Francesca] DELIVERED ✓ | {slug} | "
            f"git={git_status} | email={email_status}"
        ))],
    }


# ── Luigi: Human-in-the-loop escalation ───────────────────────────────────────
def luigi_escalate(state: StudioState) -> dict:
    reason       = state.get("escalation_reason", "unknown reason")
    product_type = state.get("product_type", "unknown_product")

    if product_type in PRICING_TABLE:
        decision = "approved"
        note     = f"AUTO-APPROVED (product in table): {reason}"
    else:
        decision = "rejected"
        note     = f"REJECTED — define price first: {reason}"

    return {
        "luigi_decision":    decision,
        "escalate_to_luigi": False,
        "finished":          decision == "rejected",
        "messages": [AIMessage(content=f"[Luigi] {note}")],
    }
