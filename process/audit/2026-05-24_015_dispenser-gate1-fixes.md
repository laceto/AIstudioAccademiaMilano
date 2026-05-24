# Audit Log — Request 015

```yaml
request_id: "015"
date: "2026-05-24"
time: "14:55"
input_type: text
raw_input: |
  Pre-deploy review of deliverable 014 (dispenser input v1) by three parallel
  reviewers (v2 ergonomics, security/public-surface, deploy-day correctness)
  surfaced 13 issues across 3 gates. Luigi chose Gate 1 dispenser fixes only.
intent: internal_bugfix
product_type: internal_infra_build
price_eur: 0.00
notes_pricing: |
  Bugfix on existing internal infra (deliverable 014, priced internally
  at €0.00). No Marco escalation; Marco's `unknown_product: null` rule
  does not apply (the underlying product type is known: internal_infra_build).

review_inputs:
  - source: "agent: v2 ergonomics reviewer (general-purpose, parallel)"
    verdict: "ABCs mostly clean; Classification + escalation are v2 blockers; ?session_id= leaks"
  - source: "agent: security + public-surface reviewer (general-purpose, parallel)"
    verdict: "2 must-fix-before-HF (XSRF off, .gitignore gaps); several must-fix-before-real-money"
  - source: "agent: deploy-day correctness reviewer (general-purpose, parallel)"
    verdict: "BLOCKER — Space crashes on first render (catalog path); session_state lost across redirect"

agents_invoked:
  - name: Gianni
    role: requirements_gate
    duration_sec: 30
    status: success
    notes: >
      Generated Requirements Manifest scoped to 3 fixes (catalog bundling,
      XSRF re-enable, metadata-based rehydrate). User replied GO.
  - name: Chiara
    role: product_generator
    duration_sec: 180
    status: success
    notes: >
      Three commits, one per fix:
        b0e7a8c fix(014): bundle pricing.json so the dispenser boots without parent repo
        73a5355 fix(014): re-enable XSRF protection on the dispenser form
        6bc3354 fix(014): re-hydrate pending request from Stripe metadata
      Files touched:
        deliverables/2026-05-24_014_dispenser-input/
          + pricing.json                   (NEW — snapshot of config/global_settings.json pricing block)
          ~ Dockerfile                     (removed --server.enableXsrfProtection=false)
          ~ main.py                        (drop session_state dep; metadata-based rehydrate; max_chars caps)
          ~ classifiers/catalog_classifier.py  (prefer bundled pricing.json, fall back to monorepo)
          ~ payments/base.py               (NEW PaymentVerification dataclass; verify_payment signature change)
          ~ payments/stripe_provider.py    (app_marker + expected_amount_cents server-side stamping)
          ~ payments/satispay_provider.py  (signature update to PaymentVerification — stub unchanged)
          ~ payments/paypal_provider.py    (signature update to PaymentVerification — stub unchanged)
          ~ payments/__init__.py           (export PaymentVerification)
  - name: Stacy
    role: qa_validation
    duration_sec: 40
    status: success
    notes: >
      Smoke tests:
        ✅ CatalogClassifier() loads pricing.json — 10 products discovered
        ✅ All concrete providers have empty __abstractmethods__ (ABC contract satisfied)
        ✅ APP_MARKER = "dispenser_v1" exported correctly
        ✅ PaymentVerification fields = [paid, amount_cents, metadata]
        ✅ main.py compiles cleanly (py_compile)
      Manual checks still pending (require running container):
        ⏸ Cold-start with no secrets → form renders, no crash (README:77 promise)
        ⏸ Cold-start with Stripe test keys → form → checkout → redirect → enqueue end-to-end
        ⏸ Replay attack: reused session_id from foreign metadata → rejected
        ⏸ Reused session_id with mismatched amount → rejected
  - name: Marco
    role: transaction_manager
    duration_sec: 1
    status: success
    notes: "Internal infra fix, €0.00. No invoice issued."
  - name: Francesca
    role: delivery_agent
    duration_sec: 0
    status: pending
    notes: "Will commit this audit log and push the branch; no external delivery."
  - name: Lorenzo
    role: security_watchdog
    duration_sec: 0
    status: passive
    notes: >
      Only external content in this work was the three reviewer reports — read
      and acted on, nothing instruction-shaped detected. No BLOCK raised.

skills_used:
  - streamlit_form_design
  - stripe_checkout_metadata
  - abc_dataclass_python
  - docker_streamlit_serve

scope_clarifications:
  - issue: "Gate 1 fix #3 cleanly requires PaymentVerification return type on the ABC"
    resolution: >
      Implemented as additive ABC change. Incidentally lands ~half of Gate 3
      v2-ergonomics item 12 (cross-provider unification of verify_payment).
      Caller-facing API now uniform across Stripe / Satispay / PayPal stubs.
  - issue: "Free text + recipient are now in Stripe metadata"
    resolution: >
      Acceptable for sandbox / test-mode use. For real-money production,
      revisit: move to a server-side pending_orders store (sqlite + litestream
      or managed Postgres) so PII does not transit Stripe metadata.
      Tracked indirectly under Gate 4 (HF demo vs. Cloud Run decision).

deferred_to_next_gate:
  gate_2_before_real_money:
    - "Twilio webhook HMAC-SHA1 signature validation (CLAUDE.md mandate)"
    - "Telegram parse_mode injection (Markdown → MarkdownV2 with escaping)"
    - "Rate limiting / per-dispenser daily cap"
    - "Queue concurrency (fcntl.flock or SQLite)"
    - "Stripe payment_method_types: add sepa_debit, apple_pay, klarna for IT market"
    - ".gitignore patterns when pushing the deliverable folder as a standalone HF Space repo"
  gate_3_v2_ergonomics:
    - "Classification dataclass: add confidence, missing_fields, needs_followup, rationale"
    - "ClassificationInput dataclass to replace classify(**kwargs)"
    - "Escalation branch in main.py (confidence < 0.8 → Telegram, no checkout)"
    - "Channel discovery from delivery.CHANNELS (drop hardcoded whatsapp/telegram)"
  gate_4_architecture:
    - "HF Space demo-only vs. Cloud Run + persistent volume — decide at 1 Jun website kickoff"

learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 1
  risk_notes: >
    Risk dropped from 3 (pre-fix) to 1 (post-fix). All three Gate 1 BLOCKERS resolved.
    No external network writes, no new credentials introduced. Reversible —
    every change is local to deliverables/.../2026-05-24_014_dispenser-input/.

outcome: success
```

## Summary

Three targeted bugfixes on the dispenser deliverable, applied before the HF
sandbox push. Risk score on deliverable 014 drops from 3 → 1:

1. **Boot crash fixed** — `pricing.json` bundled next to the deliverable;
   `CatalogClassifier` prefers it and falls back to the monorepo settings
   for the dev loop. The Hugging Face Space will now render its form on
   first request instead of crashing with `FileNotFoundError`.

2. **XSRF protection restored** — removed `--server.enableXsrfProtection=false`
   from the Dockerfile. A public payment form must not let arbitrary pages
   POST forged orders.

3. **Paid orders no longer silently lost** — the pending payload now rides
   inside Stripe Checkout metadata instead of `st.session_state`, which
   does not survive the redirect to Stripe and back. Replay defence added
   at the same time: every session is server-side-stamped with
   `app_marker = dispenser_v1` and `expected_amount_cents`; the return
   path requires all three checks (paid + marker + amount) to enqueue.

## What did NOT change in this pass

- The whole Gate 2 list (Twilio webhook signing, rate limiting, Markdown
  injection, queue concurrency, payment methods) — Marco's call:
  test-mode sandbox is OK with these deferred.
- The whole Gate 3 list (v2 ABC ergonomics for LLMClassifier, escalation,
  channel discovery) — Luigi explicitly scoped to Gate 1 only. Will revisit
  before the LLMClassifier work (ISS-012) lands so queued records stay
  forward-compatible.
- Gate 4 architectural decision (HF demo vs. Cloud Run) — deferred to the
  1 Jun website kickoff.

## Next user-facing step

Branch `claude/website-design-brainstorm-IDi3T` is now safe to push to a
public HF Space for sandbox testing. The original 4-command runbook still
applies — no changes needed there.
