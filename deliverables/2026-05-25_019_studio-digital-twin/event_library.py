"""
Pre-built event library for the Studio Digital Twin.
Each event is a structured external shock that can be injected into the simulation.
"""
from __future__ import annotations

EVENTS: dict[str, dict] = {
    "api_price_increase": {
        "type":                "api_price_increase",
        "title":               "Anthropic raises API prices 10x",
        "description":         (
            "Anthropic announces a 10x price increase on all inference endpoints, "
            "effective immediately. claude-haiku and claude-sonnet costs multiply by 10."
        ),
        "severity":            0.85,
        "affected_components": ["chiara", "marco", "all_deliverables"],
        "parameters": {
            "multiplier":       10,
            "provider":         "anthropic",
            "affected_models":  ["claude-haiku-4-5", "claude-sonnet-4-6"],
        },
    },
    "demand_spike": {
        "type":                "demand_spike",
        "title":               "10 simultaneous client requests in one hour",
        "description":         (
            "A viral LinkedIn post drives 10 simultaneous client requests within one hour. "
            "This is 10x the normal load the single-operator studio has ever handled."
        ),
        "severity":            0.70,
        "affected_components": ["stacy", "gianni", "chiara"],
        "parameters": {
            "request_count":  10,
            "window_hours":   1,
            "normal_load":    1,
        },
    },
    "api_outage": {
        "type":                "api_outage",
        "title":               "Anthropic API outage — 4 hours during business hours",
        "description":         (
            "Anthropic experiences a complete API outage lasting 4 hours during "
            "peak business hours (10:00–14:00 CET). OpenAI fallback is available."
        ),
        "severity":            0.90,
        "affected_components": ["all"],
        "parameters": {
            "provider":         "anthropic",
            "duration_hours":   4,
            "has_fallback":     True,
            "fallback":         "openai",
        },
    },
    "competitor_launch": {
        "type":                "competitor_launch",
        "title":               "Competitor launches identical service at half price",
        "description":         (
            "A well-funded startup launches an AI studio service identical to ours, "
            "priced at 50% of our catalog. Targeting the same SMB segment in Italy."
        ),
        "severity":            0.65,
        "affected_components": ["marco", "stacy"],
        "parameters": {
            "price_delta_pct": -50,
            "competitor":      "AIStudio_clone",
            "market_overlap":  0.80,
        },
    },
    "client_churn": {
        "type":                "client_churn",
        "title":               "Top 3 clients cancel simultaneously",
        "description":         (
            "The three highest-revenue clients cancel their engagements on the same day. "
            "Combined revenue loss: ~€135 in immediate pipeline + recurring risk."
        ),
        "severity":            0.75,
        "affected_components": ["marco", "francesca"],
        "parameters": {
            "clients_lost":    3,
            "revenue_lost_eur": 135,
            "reason":          "competitor offering",
        },
    },
    "gdpr_audit": {
        "type":                "gdpr_audit",
        "title":               "Italian DPA (Garante) initiates a GDPR audit",
        "description":         (
            "The Garante per la protezione dei dati personali opens a formal audit "
            "of AI Studio's handling of client data, LLM outputs, and API logs. "
            "Response required within 30 days."
        ),
        "severity":            0.80,
        "affected_components": ["compliance_agent", "francesca", "all_deliverables"],
        "parameters": {
            "authority":    "Garante",
            "scope":        "all_client_data",
            "deadline_days": 30,
        },
    },
    "war_underwriting": {
        "type":                "war_underwriting",
        "title":               "Armed conflict declared in primary underwriting territory",
        "description":         (
            "A declared armed conflict erupts in a territory covering 35% of the studio's "
            "active client base. Contracts under force majeure; delivery SLAs suspended. "
            "(Insurance vertical simulation — adapt parameters for your client.)"
        ),
        "severity":            0.95,
        "affected_components": ["all"],
        "parameters": {
            "territory_coverage_pct": 35,
            "force_majeure":          True,
            "duration_estimate_days": 90,
            "contracts_at_risk":      5,
        },
    },
    "key_person_unavailable": {
        "type":                "key_person_unavailable",
        "title":               "Luigi unavailable for 30 days (illness / travel)",
        "description":         (
            "The sole operator (Luigi) is unavailable for 30 days. "
            "All pipeline decisions require asynchronous approval. "
            "No new deliverables can be authorised without Luigi."
        ),
        "severity":            0.85,
        "affected_components": ["all"],
        "parameters": {
            "person":           "Luigi",
            "duration_days":    30,
            "automation_level": 0.60,
        },
    },
}


def get_event(key: str) -> dict:
    if key not in EVENTS:
        raise KeyError(f"Unknown event: {key!r}. Available: {list(EVENTS)}")
    return EVENTS[key]


def event_labels() -> dict[str, str]:
    return {k: v["title"] for k, v in EVENTS.items()}
