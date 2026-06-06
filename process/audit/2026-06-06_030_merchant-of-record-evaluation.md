```yaml
request_id: "030"
date: "2026-06-06"
intent: merchant_of_record_evaluation
product_type: strategic_report
outcome: success
agents_invoked:
  - name: deep-research
    role: multi-source web research
    action: "5 parallel search agents covering LS fees, LS API/payout, Payhip fees/VAT, Payhip API/risks, LS vs Payhip comparison + AI content"
    duration_sec: 550
    status: completed
skills_used:
  - deep-research
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 2
```

# ISS-025 — Merchant-of-Record Evaluation: Lemon Squeezy vs Payhip

**Date:** 2026-06-06  
**Scope:** EU VAT merchant-of-record platform selection for AI Studio Accademia Milano  
**Product catalog:** Digital deliverables priced €1.90–€45.90 (PDF, landing pages, chatbot apps, RAG, planners, etc.)  
**Primary market:** Italian and EU consumers/SMBs

---

## Recommendation: **Payhip (Free tier → Plus when volume > €850/mo)**

Payhip is the better fit for this studio on every axis that matters for the current product catalog and Italian customer base. The key differentiators are: explicit AI-content policy, better economics at low ticket prices, instant payouts, and no acquisition-driven strategic uncertainty.

---

## 1. EU VAT / Merchant-of-Record Coverage

Both platforms act as MoR and handle EU VAT automatically, but with different scope:

| Platform | EU VAT | UK VAT | US Sales Tax | Other jurisdictions |
|---|---|---|---|---|
| **Lemon Squeezy** | ✅ Full (OSS/IOSS) | ✅ | ✅ | ✅ Growing list |
| **Payhip** | ✅ Full (MoR for EU/UK) | ✅ | ❌ Seller's responsibility | Limited |

For a studio selling primarily to Italian and EU buyers, **both platforms cover the core requirement**. Payhip's gap (US sales tax) only matters if the studio targets US customers at scale — not the current case.

Neither platform requires the seller to register for VAT in Germany, France, or any other EU country. The platform remits VAT as the legal seller of record.

---

## 2. Fee Comparison at Studio Price Points

Using EUR/USD ≈ 1.08, all EU-customer scenarios:

### Lemon Squeezy (EU customers): 6.5% + $0.50
The advertised "5% + 50¢" is for US customers. EU buyers trigger the mandatory +1.5% international surcharge, making the real rate **6.5% + $0.50** on every Italian sale.

### Payhip Free: 5% + Stripe processor (~2.9% + $0.30)
Total effective: ~7.9% + $0.30

| Product | Price | LS nets (€) | Payhip Free nets (€) | Winner |
|---|---|---|---|---|
| `pdf_document` | €1.90 | €1.30 (31% fee!) | €1.47 (23% fee) | **Payhip** |
| `invoice_pdf` | €3.90 | €3.18 (18% fee) | €3.31 (15% fee) | **Payhip** |
| `strategic_report` | €4.90 | €4.07 (17% fee) | €4.19 (14% fee) | **Payhip** |
| `weather_dashboard` | €9.90 | €8.79 (11% fee) | €8.83 (11% fee) | Tie |
| `calendar_integration` | €14.90 | €13.46 (10% fee) | €13.44 (10% fee) | Tie |
| `chatbot_app` | €19.90 | €18.14 (9% fee) | €18.04 (9% fee) | Tie |
| `algo_trading` | €24.90 | €22.81 (8% fee) | €22.66 (9% fee) | **LS** |
| `rag_knowledge_base` | €29.90 | €27.49 (8% fee) | €27.23 (9% fee) | **LS** |
| `commercial_landing_page` | €45.90 | €42.45 (8% fee) | €41.99 (8% fee) | **LS** |

**Key insight:** Payhip wins on the high-volume low-ticket products (PDFs, reports). LS is marginally better only above ~€20. Since ~60% of expected transactions are in the €1.90–€14.90 band, **Payhip Free dominates on average revenue per transaction.**

### Payhip Plus ($29/mo): 2% + processor (4.9% + $0.30 total)
Breakeven vs Payhip Free: ~$967/month gross revenue. Once the studio reaches ~€900/month, upgrade to Plus and keep 95% of gross on every product.

---

## 3. AI-Generated Content Policy

| Platform | AI Content Allowed? | Risk |
|---|---|---|
| **Payhip** | ✅ Explicitly permitted | Low |
| **Lemon Squeezy** | ⚠️ Grey zone | Medium-High |

Lemon Squeezy bans PLR (private label rights) content and has an IP clause that has been used to suspend stores selling AI-generated deliverables. No explicit allowlist for AI content exists in their ToS. Post-Stripe acquisition, enforcement has become more conservative.

Payhip explicitly permits AI-generated content in their acceptable use policy. For a studio whose entire product catalog is AI-generated, this removes a significant account risk.

---

## 4. Payout Timing and Currency

| | Lemon Squeezy | Payhip |
|---|---|---|
| **Timing** | Net-15 to net-30, twice/month | Instant (Stripe) / Within days (PayPal) |
| **Currency** | USD → EUR at payout | GBP/EUR/USD depending on account |
| **Min threshold** | Not published (est. $50) | None stated |
| **FX risk** | High — all USD, converted at payout | Low — EUR Stripe SEPA available |

For an Italian seller on Payhip, payouts go via Stripe SEPA in EUR with no intermediate USD conversion step. This eliminates FX exposure entirely. Lemon Squeezy requires USD conversion at every payout cycle.

---

## 5. Integration Complexity (FastAPI/Python backend)

### Payhip integration path
```
Customer purchase on Payhip storefront
  → Payhip webhook POST to gateway/webhook/payhip
  → HMAC-SHA256 signature verification
  → Map webhook payload → PipelineAdapter.submit()
  → Trigger delivery pipeline → push deliverable to customer download URL
```

Payhip webhooks: `purchase.completed`, `purchase.refunded`, `license.activated`, `license.deactivated`  
Signature: `X-Payhip-Signature` header, HMAC-SHA256  
API: Thin (license key generation, coupon management) — sufficient for digital delivery

No official Python SDK exists for either platform. Both require direct HTTP calls (httpx).

### Lemon Squeezy integration path
Identical webhook topology. LS provides a richer API (subscriptions, product management, customer portal) — useful if the studio adds SaaS subscriptions, but unnecessary for current one-off digital products.

**Integration effort is equal.** Neither requires more than ~200 lines of webhook handler code.

---

## 6. Platform Risk Assessment

| Risk | Lemon Squeezy | Payhip |
|---|---|---|
| Account suspension (AI content) | 🔴 Medium-High | 🟢 Low |
| Strategic uncertainty | 🔴 High (Stripe acquisition, maintenance mode) | 🟡 Medium (bootstrapped, slower dev) |
| Payout hold / freeze | 🔴 Reported (2025, post-acquisition) | 🟡 Occasional (thin support) |
| GDPR / data sovereignty | 🟡 DPA exists but CLOUD Act applies | 🟡 UK entity, GDPR DPA |
| Feature deprecation | 🔴 Likely (Stripe Managed Payments migration) | 🟢 Stable feature set |

Lemon Squeezy's post-Stripe-acquisition risk profile is the deciding factor when combined with the AI content grey zone. The studio should not build its revenue infrastructure on a platform in maintenance mode with unclear long-term strategy.

---

## 7. Decision Matrix

| Criterion | Weight | LS Score | Payhip Score |
|---|---|---|---|
| EU VAT MoR coverage | 25% | 9 | 9 |
| Effective fees at studio price points | 25% | 7 | 8 |
| AI content policy | 20% | 4 | 9 |
| Payout timing & currency | 15% | 5 | 9 |
| Platform stability / strategic risk | 10% | 4 | 7 |
| Integration complexity | 5% | 7 | 7 |
| **Weighted total** | | **6.35** | **8.50** |

---

## 8. Recommended Action Plan

1. **Immediately:** Open a Payhip account (Free tier, no monthly cost). Upload 2–3 test products (PDF document, strategic report, landing page template) to validate checkout UX and webhook delivery.

2. **Week 1:** Wire `gateway/bot_whatsapp.py` and `gateway/bot_telegram.py` to a new `gateway/webhook_payhip.py` handler. Map `purchase.completed` → `PipelineAdapter.submit()` with `channel="payhip"`.

3. **At ~€850/month gross:** Upgrade to Payhip Plus ($29/mo, 2% + processor) to cut effective fee from 7.9% to 4.9% on all products.

4. **Hedge (optional):** Keep a dormant Lemon Squeezy account for non-EU customers (US, APAC) if international expansion begins. LS's global tax coverage is superior for non-EU jurisdictions where Payhip doesn't act as MoR.

5. **Do not use:** Gumroad (10% fee kills margin on €1.90 PDFs), Paddle (high revenue minimums for onboarding).

---

## 9. New Intent to Scope (spawns ISS-023/024)

The research surfaced "digital product listing pack" and "Etsy/Payhip product setup" as natural upsell intents. See ISS-023 and ISS-024 for scoping.

---

*Research sources: Lemon Squeezy docs (fees, VAT, MoR, payouts, currencies, supported countries), Payhip pricing page, Payhip acceptable use policy, TechCrunch Stripe/LS acquisition (July 2024), Lemon Squeezy 2025/2026 blog updates, BuildMVPFast/GlobalSolo/Swell/DodoPayments fee comparisons, Trustpilot reviews, Vatly.com comparison, Fungies.io acquisition analysis.*
