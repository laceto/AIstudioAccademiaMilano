# templates/web

Reusable building blocks for static-site + light-webhook deliverables.
Extracted by the V2 Team (`agents/v2_team/`) from request 011 (Forno di Marta v2).
First commercial user will get these for free — that's the point of the extraction.

## Contents

| File | Purpose | First user |
|---|---|---|
| `order_webhook.py` | Framework-agnostic order webhook. Validation + composition + injectable email/calendar dispatchers. 28 passing tests in `tests/test_iss011_order_webhook.py`. | Request 011 v2 |
| `landing_page_base.html` | Semantic HTML5 shell with JSON-LD slot, OG/Twitter cards, accessibility landmarks, optional Plausible/Sentry slots. Token-based fill-in. | Request 011 v2 |
| `decap_cms_config_minimal.yml` | Base Decap CMS config for a single content collection + single info file. | Request 011 v2 |

## How Chiara should use these

Per Core Architect guidance: **prefer extending these over re-rolling**. When Gianni's spec for a new request mentions "landing page" or "small site with content updates" or "order form to email/calendar", the second step in Chiara's plan should be `cp templates/web/* deliverables/<new-request>/site/` and then customise.

If a future deliverable forces a *third* incompatible pattern for the same job, that's a Core Architect block condition — see `agents/v2_team/core_architect.md`.

## Provenance

- Request 011 audit log: `process/audit/2026-05-24_011_bakery-v2.md`
- Critique that motivated the extraction: `deliverables/2026-05-24_011_bakery-v2/critique_of_001.md` (Core Architect section)
- Reference build using all three: `deliverables/2026-05-24_011_bakery-v2/`
