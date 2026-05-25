# Business Wiki — AI Studio Accademia Milano

> One-founder AI enterprise. Every request becomes a deployed output in under 2 minutes.

---

## Positioning

**What we are:** A micro-agency that ships software, not proposals.  
**Differentiator:** 6-agent AI pipeline turns any text input into a deployed product — website, PDF, chatbot, calendar sync — while the client is still present.  
**Distribution:** Physical dispenser (QR code → pay → receive link). No sales calls. No onboarding.  
**Target:** Small businesses in Milan who need digital products but can't afford a developer.

---

## Revenue Model

### Dispenser (primary — ISS-011)

```
Client scans QR  →  Streamlit form  →  Stripe payment  →  Pipeline builds  →  Email/WhatsApp delivery
```

- Payment processed via Stripe before build starts
- No credit risk — delivery only after payment clears
- All prices fixed (see `wiki/studio/04_pricing.md`)

### Custom (secondary)

- Luigi quotes directly, builds on the same pipeline
- Minimum: €9.90 (static landing page)
- All custom work goes through the 6-agent pipeline — no ad-hoc delivery

### Internal / R&D

- Pipeline infrastructure builds (dispenser, RAG, Research Department)
- Logged at €0.00 — not invoiced but audit-logged
- Justification: every internal build reduces future delivery cost

---

## Financials

### Invoiced to date (2026-05-25)

| Cohort | Requests | Revenue |
|--------|----------|---------|
| Day 1 (2026-05-23) | 8 | €99.80 |
| Day 2 (2026-05-24) | 5 | €35.60 |
| **Total** | **13** | **€135.40** |

### Collected: €0.00

Blocked by: **ISS-011** — Partita IVA not yet open. Stripe account requires Italian VAT registration before payouts activate. No client invoices issued yet.

### Margin model

| Cost component | Per request est. |
|----------------|-----------------|
| Claude API (Chiara + Stacy) | €0.05 – €0.30 |
| OpenAI API (embeddings, fallback) | €0.01 – €0.05 |
| Hosting (Streamlit Cloud free, Vercel free) | €0.00 |
| Stripe fee (2.9% + €0.30) | €0.58 avg on €9.90 |
| **Total COGS** | ~€0.90 avg |
| **Gross margin** | ~€9.00 on €9.90 SKU (**91%**) |

---

## Legal & Compliance

### Partita IVA (ISS-011) — OPEN P1

- Required before: issuing invoices, activating Stripe payouts, collecting revenue
- Regime: **Regime Forfettario** (flat-rate, 15% substitutive tax on 67% of revenue = ~10% effective tax)
- Action: apply via commercialista or directly via Agenzia delle Entrate online
- Est. time to activate: 1–4 weeks once applied
- Threshold: €85,000/year revenue cap to stay in forfettario

### Invoicing rules (post-IVA)

- Invoices must include: Partita IVA, client fiscal code, service description, date, amount
- Electronic invoicing (fatturazione elettronica) mandatory for B2B in Italy
- Platform: Fatture in Cloud or Aruba (integrate with Marco's invoice template)

### Privacy / GDPR

- No personal data stored beyond the session (credential manager TTL: session-scoped)
- Dispenser collects: email or WhatsApp number for delivery — minimal, necessary, disclosed
- No analytics without consent — Streamlit Cloud provides no tracking by default

---

## Banking

### Current setup

| Account | Purpose | Status |
|---------|---------|--------|
| Personal (Intesa/UniCredit) | Studio expenses | Active |
| Stripe | Payment collection | Pending (needs Partita IVA) |

### Target setup

| Account | Purpose |
|---------|---------|
| **Qonto** (business current) | Primary studio account — IBAN for invoices, card for expenses |
| **Wise** (multi-currency) | International clients, USD API billing, PayPal alternative |
| **Stripe** | Card payments at dispenser and online |

### Why Qonto

- Italian IBAN + Mastercard business card in 1 day
- Built-in expense categorisation — useful for forfettario bookkeeping
- No minimum balance, ~€9/month
- API access for auto-reconciliation with Marco's invoice system (future)

---

## Growth Path

```
Phase 1 (now):     Pipeline proven, pricing validated, 13 requests in 2 days
Phase 2 (Q3 2026): Dispenser live, Partita IVA open, first paying clients
Phase 3 (Q4 2026): 2nd dispenser location, recurring clients (maintenance SKU)
Phase 4 (2027):    White-label pipeline for other micro-agencies
```

### Metrics to track

| Metric | Target (Phase 2) |
|--------|-----------------|
| Requests / week | 20 |
| Revenue / week | €200 |
| Avg margin | >85% |
| Pipeline success rate | >95% |
| Time to deliver | <3 min |
