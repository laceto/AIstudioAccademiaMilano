"""
Avvocato AI — LangGraph node functions.

Every node accepts (state, config) — LangGraph injects config automatically.
provider is read from config["configurable"]["provider"] (default: "anthropic").

  fast tier  → haiku-4.5 / gpt-4o-mini  (intake, QA, compliance)
  smart tier → sonnet-4.6 / gpt-4o      (research, drafting)
"""
import json
import uuid
from datetime import datetime

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .llm_factory import get_llm
from .state import (
    BILLING_RATES,
    DISCLAIMER_IT,
    MATTER_TYPES,
    LawyerState,
)


def _provider(config: RunnableConfig) -> str:
    return (config or {}).get("configurable", {}).get("provider", "anthropic")


# ── 1. Intake Agent ────────────────────────────────────────────────────────────
def intake_agent(state: LawyerState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Sei un assistente legale dello Studio Legale.
Analizza la richiesta e restituisci SOLO JSON valido:
{{
  "matter_type": "penale|civile|contrattuale|societario|famiglia|immobiliare|lavoro|unknown",
  "urgency": "urgente|standard|bassa_priorita",
  "jurisdiction": "IT|EU|other",
  "intake_summary": "Riassunto in 2-3 frasi del caso",
  "document_type": "parere|contratto|atto|lettera|clausola"
}}"""),
        ("human", "Richiesta: {request}\nNome: {name}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "request": state["client_request"],
        "name":    state.get("client_name", "Cliente"),
    })

    matter       = result.get("matter_type", "unknown")
    matter_label = MATTER_TYPES.get(matter, matter)

    return {
        "matter_type":    matter,
        "urgency":        result.get("urgency", "standard"),
        "jurisdiction":   result.get("jurisdiction", "IT"),
        "intake_summary": result.get("intake_summary", ""),
        "document_type":  result.get("document_type", "parere"),
        "messages": [AIMessage(content=(
            f"[Intake] materia={matter_label} | "
            f"urgenza={result.get('urgency')} | "
            f"giurisdizione={result.get('jurisdiction')} | "
            f"tipo_doc={result.get('document_type')}"
        ))],
    }


# ── 2. Legal Researcher ────────────────────────────────────────────────────────
def legal_researcher(state: LawyerState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "smart", max_tokens=4096, temperature=0.1)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Sei un ricercatore legale specializzato in diritto italiano ed europeo.
Individua normativa e giurisprudenza rilevante.
Restituisci SOLO JSON valido:
{{
  "legal_research": {{
    "normativa_applicabile": ["art. X c.c. — ...", "D.Lgs. Y/ANNO — ..."],
    "principi_giurisprudenziali": ["Cass. civ. sez. X, n. YYYY — ..."],
    "note_pratiche": "..."
  }},
  "relevant_articles": ["art. 1218 c.c.", "art. 2697 c.c."],
  "relevant_cases": ["Cass. civ. n. 12345/2023"],
  "research_confidence": 0.85
}}"""),
        ("human", (
            "Materia: {matter_type}\n"
            "Giurisdizione: {jurisdiction}\n"
            "Riassunto: {summary}\n"
            "Richiesta: {request}"
        )),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "matter_type":  MATTER_TYPES.get(state.get("matter_type", "unknown"), ""),
        "jurisdiction": state.get("jurisdiction", "IT"),
        "summary":      state.get("intake_summary", ""),
        "request":      state["client_request"],
    })

    return {
        "legal_research":      result.get("legal_research", {}),
        "relevant_articles":   result.get("relevant_articles", []),
        "relevant_cases":      result.get("relevant_cases", []),
        "research_confidence": result.get("research_confidence", 0.7),
        "messages": [AIMessage(content=(
            f"[Ricercatore] articoli={result.get('relevant_articles')} | "
            f"casistica={result.get('relevant_cases')} | "
            f"confidenza={result.get('research_confidence', 0):.0%}"
        ))],
    }


# ── 3. Document Drafter ────────────────────────────────────────────────────────
def document_drafter(state: LawyerState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "smart", max_tokens=8192, temperature=0.1)

    doc_labels = {
        "parere": "parere legale", "contratto": "bozza di contratto",
        "atto": "atto giuridico",  "lettera": "lettera legale",
        "clausola": "clausola contrattuale",
    }
    doc_label = doc_labels.get(state.get("document_type", "parere"), "documento legale")

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""Sei un avvocato italiano esperto. Redigi un {doc_label} professionale.

Struttura:
- Intestazione: Studio Legale, data, rif. pratica
- Premessa in fatto
- Analisi giuridica (cita le norme trovate)
- Conclusioni / raccomandazioni
- Firma: "Avv. [Nome]"
- OBBLIGATORIO in fondo (verbatim):
  {DISCLAIMER_IT}

Usa linguaggio giuridico formale italiano.
Restituisci SOLO JSON valido:
{{
  "draft_document": "...testo completo...",
  "disclaimer_included": true
}}"""),
        ("human", (
            "Cliente: {client_name}\n"
            "Richiesta: {request}\n"
            "Ricerca: {research}\n"
            "Articoli: {articles}"
        )),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "client_name": state.get("client_name", "Egregio Cliente"),
        "request":     state["client_request"],
        "research":    json.dumps(state.get("legal_research", {}), ensure_ascii=False),
        "articles":    str(state.get("relevant_articles", [])),
    })

    draft = result.get("draft_document", "")
    if DISCLAIMER_IT[:40] not in draft:
        draft = draft.rstrip() + "\n\n" + DISCLAIMER_IT

    return {
        "draft_document":     draft,
        "disclaimer_included": True,
        "messages": [AIMessage(content=(
            f"[Redattore] {len(draft)} caratteri | disclaimer={'sì' if DISCLAIMER_IT[:20] in draft else 'MANCANTE!'}"
        ))],
    }


# ── 4a. Legal QA ──────────────────────────────────────────────────────────────
def legal_qa(state: LawyerState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Sei un avvocato senior che revisiona il documento. Verifica:
1. Accuratezza giuridica (norme citate corrette?)
2. Coerenza con la giurisdizione
3. Completezza
4. Disclaimer presente?

Return ONLY valid JSON: {{"passed": true, "issues": [], "reviewer": "legal_qa"}}"""),
        ("human", "Documento: {doc}\nGiurisdizione: {jur}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "doc": (state.get("draft_document") or "")[:3000],
        "jur": state.get("jurisdiction", "IT"),
    })
    result["reviewer"] = "legal_qa"

    return {
        "review_reports": [result],
        "messages": [AIMessage(content=(
            f"[LegalQA] {'OK' if result.get('passed') else 'PROBLEMI: ' + str(result.get('issues'))}"
        ))],
    }


# ── 4b. Compliance Check ──────────────────────────────────────────────────────
def compliance_check(state: LawyerState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=1024, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Sei un compliance officer legale. Verifica:
1. GDPR: dati personali gestiti correttamente?
2. Codice Deontologico Forense rispettato?
3. Rischio esercizio abusivo della professione (AI)?
4. Disclaimer di responsabilità presente?

Return ONLY valid JSON: {{"passed": true, "issues": [], "reviewer": "compliance_check"}}"""),
        ("human", "Documento: {doc}"),
    ])

    result: dict = (prompt | llm | JsonOutputParser()).invoke({
        "doc": (state.get("draft_document") or "")[:2000],
    })
    result["reviewer"] = "compliance_check"

    return {
        "review_reports": [result],
        "messages": [AIMessage(content=(
            f"[Compliance] {'OK' if result.get('passed') else 'PROBLEMI: ' + str(result.get('issues'))}"
        ))],
    }


# ── 5. QA Merge ───────────────────────────────────────────────────────────────
def qa_merge(state: LawyerState) -> dict:
    reports    = state.get("review_reports", [])
    all_issues = [issue for r in reports if not r.get("passed", True) for issue in r.get("issues", [])]
    passed     = all(r.get("passed", True) for r in reports)

    return {
        "qa_passed":  passed,
        "qa_issues":  all_issues if all_issues else None,
        "messages": [AIMessage(content=(
            f"[QA Merge] {'PASS ✓' if passed else 'FAIL — ' + str(all_issues)}"
        ))],
    }


# ── 6. Billing Agent ──────────────────────────────────────────────────────────
def billing_agent(state: LawyerState) -> dict:
    matter = state.get("matter_type", "unknown")
    rates  = BILLING_RATES.get(matter, BILLING_RATES["unknown"])

    doc_len         = len(state.get("draft_document") or "")
    estimated_hours = max(rates["min_hours"], round(doc_len / 2000, 1))
    hourly          = rates["hourly"]
    total_fee       = round(estimated_hours * hourly, 2)
    iva             = round(total_fee * 0.22, 2)
    cpa             = round(total_fee * 0.04, 2)
    grand_total     = round(total_fee + iva + cpa, 2)

    invoice_id = f"PROT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    invoice = {
        "invoice_id":         invoice_id,
        "client":             state.get("client_name", "Cliente"),
        "matter_type":        MATTER_TYPES.get(matter, matter),
        "document_type":      state.get("document_type", "parere"),
        "onorario_base_eur":  total_fee,
        "iva_22_eur":         iva,
        "cpa_4_eur":          cpa,
        "totale_eur":         grand_total,
        "ore_stimate":        estimated_hours,
        "tariffa_oraria_eur": hourly,
        "data":               datetime.now().strftime("%d/%m/%Y"),
        "status":             "da_pagare",
    }

    return {
        "billing_type":    "orario",
        "hourly_rate":     hourly,
        "estimated_hours": estimated_hours,
        "total_fee":       grand_total,
        "invoice":         invoice,
        "messages": [AIMessage(content=(
            f"[Fatturazione] {estimated_hours}h × €{hourly}/h + IVA + CPA = €{grand_total} | {invoice_id}"
        ))],
    }


# ── 7. Delivery Agent ─────────────────────────────────────────────────────────
def delivery_agent(state: LawyerState) -> dict:
    method = state.get("contact_method", "email")
    channel_notes = {
        "email":          "Email con documento PDF allegato [simulato]",
        "discord":        "DM Discord — ideale per gaming clients su PS5/Xbox [simulato]",
        "whatsapp":       "WhatsApp con link sicuro al documento [simulato]",
        "portale_sicuro": "Portale client con link protetto [simulato]",
    }

    result = {
        "channel":    method,
        "note":       channel_notes.get(method, "Consegna generica [simulata]"),
        "invoice_id": state.get("invoice", {}).get("invoice_id", ""),
        "timestamp":  datetime.now().isoformat(),
        "status":     "consegnato",
    }

    return {
        "delivery_result": result,
        "finished":        True,
        "messages": [AIMessage(content=(
            f"[Consegna] {method} | {channel_notes.get(method, '')} | pratica={result['invoice_id']}"
        ))],
    }
