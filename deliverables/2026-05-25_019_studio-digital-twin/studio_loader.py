"""
Loads the live state of AI Studio Accademia Milano from config files.
This is the digital twin's baseline — what the studio looks like *right now*
before any external shock is applied.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

_KNOWN_REVENUES = [
    9.90,   # 001 bakery website
    2.40,   # 002 pdf + email
    3.90,   # 003 invoice pdf + email
    4.90,   # 004 strategic report
    19.90,  # 005 chatbot
    29.90,  # 006 rag
    14.90,  # 007 calendar
    24.90,  # 008 algo trading
    4.90,   # 009 linkedin post
    14.90,  # 010 profile setup
    9.90,   # 011 weather dashboard
    0.00,   # 012 discord bot (internal)
    19.90,  # 013 techa deploy
    0.00,   # 014 dispenser (internal infra)
    0.00,   # 015 logo generator (internal)
    0.00,   # 016 aistudio langgraph (internal)
    0.00,   # 017 lawyer langgraph (internal)
    0.00,   # 018 soap note (internal)
    0.00,   # 019 digital twin (internal)
    9.90,   # 020 mind dashboard
    14.90,  # 021 micro syllabus
    14.90,  # 022 family archivist
    14.90,  # 023 meal planner
    14.90,  # 024 niccolò chronicles
    0.00,   # 025 chat rss (internal)
    24.90,  # 026 trading agent team
    4.90,   # 027 diy electrical brainstorm
    0.00,   # 028 team showcase (internal)
    0.00,   # 029 reinsurance office (internal)
]

_PRICING_TABLE = {
    "static_landing_page":        9.90,
    "premium_landing_page":       29.90,
    "commercial_landing_page":    45.90,
    "pdf_document":               1.90,
    "invoice_pdf":                3.90,
    "strategic_report":           4.90,
    "chatbot_app":                19.90,
    "email_delivery":             0.50,
    "rag_knowledge_base":         29.90,
    "calendar_integration":       14.90,
    "weather_dashboard":          9.90,
    "agent_deploy_streamlit":     19.90,
    "algo_trading":               24.90,
    "mind_dashboard_journal":     9.90,
    "micro_syllabus_flashcards":  14.90,
    "family_archivist":           14.90,
    "mediterranean_meal_planner": 14.90,
    "niccolo_chronicles":         14.90,
}


def load_studio_baseline() -> dict:
    settings_path = REPO_ROOT / "config" / "global_settings.json"
    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}

    meta   = settings.get("_meta", {})
    skills = settings.get("skills", {})

    total_revenue   = sum(_KNOWN_REVENUES)
    paid            = [r for r in _KNOWN_REVENUES if r > 0]
    avg_revenue     = round(total_revenue / len(paid), 2) if paid else 0.0

    return {
        "version":                       meta.get("version", "1.8"),
        "last_updated":                  meta.get("last_updated", "2026-05-25"),
        "total_requests_processed":      meta.get("total_requests_processed", 17),
        "skills_count":                  len(skills) or 38,
        "pricing_table":                 _PRICING_TABLE,
        "total_revenue_eur":             round(total_revenue, 2),
        "avg_revenue_per_request_eur":   avg_revenue,
        "estimated_monthly_api_cost_eur": 12.50,
        "primary_llm_provider":          "anthropic",
        "fallback_llm_provider":         "openai",
        "pipeline_agents":               ["stacy", "gianni", "chiara", "marco", "francesca"],
        "risk_agents":                   ["technical_auditor", "compliance_agent", "reputation_guardian"],
        "delivery_channels":             ["streamlit", "github", "vercel", "telegram", "whatsapp"],
        "open_issues_count":             22,
        "open_p1_issues":                5,
        "pipeline_health_pct":           95,
        "team_size":                     1,
        "sku_count":                     len(_PRICING_TABLE),
    }


def load_studio_state_node(state: dict) -> dict:
    """LangGraph node: injects studio_baseline if not already present."""
    if state.get("studio_baseline"):
        return {}
    return {"studio_baseline": load_studio_baseline()}
