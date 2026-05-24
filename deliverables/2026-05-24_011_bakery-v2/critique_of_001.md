# Critique of Request 001 — Forno di Marta v1

> Produced by the V2 Team (`agents/v2_team/`) on 2026-05-24 in response to Luigi's request to "work on better delivery and higher delivery value for the first deliverable 001 bakery."
>
> Source material: `process/audit/2026-05-23_001_bakery-website.md` and `deliverables/2026-05-23_001_bakery-website/`.

## TL;DR

The v1 ships, but it ships with a known placeholder (`bakery.jpg`), no observability, no SEO surface, no business schema, and no integration with the studio's own products (Gmail send from 002, calendar sync from 007). Marco priced it at €9.90 — defensible at the time; the v2 unlocks a higher tier (Luigi to set) by turning a brochure into a small commercial surface.

---

## 1. Quality Reliability Lead

### Shipped defects

| # | Defect | Evidence | Severity |
|---|---|---|---|
| QRL-1 | `bakery.jpg` placeholder shipped to production | `qa_notes: "bakery.jpg is a placeholder image — noted for user"` (001 audit) | P2 — visible to every visitor |
| QRL-2 | Contact form action contains literal string `YOUR_FORM_ID` until user edits it | `index.html` line: `action="https://formspree.io/f/YOUR_FORM_ID"` | P1 — form silently broken on first deploy |
| QRL-3 | Tailwind loaded via CDN at runtime (`https://cdn.tailwindcss.com`) | `index.html` `<script src="...">` | P3 — render-blocking, dev-mode CSS in production |
| QRL-4 | No automated tests of any kind | `tests/` has no `test_iss001*` or `test_bakery*` | P2 |

### Missing SLOs (what should have existed)

| Metric | Target for a €9.90 landing page | Current |
|---|---|---|
| Lighthouse Performance | >= 90 | unmeasured |
| Lighthouse Accessibility | >= 95 | unmeasured |
| Page weight | < 300 KB | ~600 KB (Tailwind CDN runtime ~370 KB by itself) |
| Uptime | >= 99.5% (Vercel free tier covers this) | unmeasured |
| Form submission success rate | >= 99% | unmeasured (Formspree exposes it; nobody is reading it) |

### Required tests for v2

1. Smoke test: HTML parses, all internal anchors resolve, no `YOUR_FORM_ID` literal remains.
2. JSON-LD validation: schema.org `LocalBusiness` blob parses and contains required fields.
3. Webhook contract test: `POST /order` with valid payload returns 200 + `order_id`; with invalid email returns 400.
4. Lighthouse CI on PR: fail build if Performance < 85 or Accessibility < 95.
5. axe-core a11y scan in CI.

### Observability stack (recommended, cheapest tier)

| Tool | What it covers | Monthly cost |
|---|---|---|
| Plausible | Page views, conversion events on form submit | €9 (Plausible Cloud) or €0 self-hosted |
| Sentry (free tier) | JS errors on the page + webhook errors | €0 |
| Vercel built-in analytics | Edge latency, deploy health | €0 (Hobby plan) |
| UptimeRobot | 5-minute pings, alerts on downtime | €0 (free tier covers single endpoint) |

**QRL block condition**: v2 must not ship without Lighthouse Performance >= 70 and Sentry on the order webhook.

---

## 2. Core Architect

### Stack regrets

| Choice in v1 | Why questionable | Alternative for v2 | Migration cost |
|---|---|---|---|
| Tailwind via CDN | The CDN build is dev-only per Tailwind's own docs. Ships ~370 KB of unused CSS to every visitor. | Compile a tiny `tailwind.css` (~12 KB) via the Play CDN extract or `npx tailwindcss -i in.css -o out.css --minify`. Or drop Tailwind for vanilla CSS at this size. | Low — one build step or one CSS file. |
| Alpine.js implicit | Audit log lists `alpine_js` as a skill but the v1 `index.html` doesn't actually use Alpine. | Remove. v2 doesn't need it either. | Trivial. |
| Formspree | Third-party vendor. Breaks our own integration story — we already own `gmail_api_send` (002). | Internal webhook that uses our Gmail send skill + writes the order to a calendar event via 007's adapter. | Medium — one Python handler, ~80 LOC. |
| Hero image as local file | `bakery.jpg` shipped as a placeholder. No image pipeline. | Either Cloudinary/Vercel image optimisation, or a CMS-managed asset with `<picture>` + AVIF/WebP fallback. | Low. |
| No build step | Every change is a hand-edit of one HTML file. No content/presentation split. | Decap CMS (Git-backed, free) writes Markdown that the site reads at build time. The bakery edits content; Chiara never edits content again. | Medium — Decap config + one build script. |

### Coupling findings

The v1 re-implements two capabilities that other deliverables already own:

- **Form-to-email**: v1 uses Formspree. Deliverable 002 owns `gmail_api_send`. v1 should have called it.
- **Booking/calendar**: v1 has no booking surface, yet deliverable 007 ships a multi-provider calendar sync. The bakery is precisely the kind of business that would use it (cake orders, event catering, pickup slots). v2 wires this in.

### Reusables to extract (proposed `templates/` modules)

1. `templates/web/landing_page_base.html` — semantic shell with JSON-LD slot, OG tags, Plausible snippet, Sentry boot. Reuse for any future static site.
2. `templates/web/order_form_to_gmail_calendar.py` — generic webhook (form schema in, Gmail confirmation + calendar event out). The bakery is the first user; the next one will be free.
3. `templates/web/decap_cms_config_minimal.yml` — base Decap config for a single-collection content site.

### Build/deploy story for v2

```bash
cd deliverables/2026-05-24_011_bakery-v2/site
npx tailwindcss -i ./src/in.css -o ./out.css --minify   # ~2s
# static; deploy to Vercel with `vercel --prod` (existing skill)
# webhook: deploy to Vercel Functions or Cloud Run (skill from 010)
```

**Core Architect block condition**: v2 must reuse the Gmail send skill from 002 and the calendar sync from 007. Re-rolling a third email/calendar path is blocked.

---

## 3. API Product Designer

### Surface inventory (v1 vs v2)

| Surface | v1 state | v2 target |
|---|---|---|
| Public URL | `forno-di-marta.vercel.app` | same, plus `/admin` for CMS |
| Contact form | Formspree -> Marta's inbox (if she configured it) | Internal webhook -> Gmail confirmation + calendar event |
| JSON-LD | absent | `LocalBusiness` with address, geo, openingHours, telephone |
| Open Graph / Twitter cards | absent | full set (title, description, image, type=website) |
| OG image | absent | branded 1200x630 SVG -> PNG |
| sitemap.xml | absent | generated at build |
| robots.txt | absent | minimal `Allow: /` + sitemap pointer |
| RSS / events feed | absent | optional `/events.xml` if Marta posts seasonal items |

### Conversion path

v1: visitor -> reads -> (maybe) emails Marta via Formspree -> ???. No measurement, no closed loop.

v2:
```
Visitor lands
   |
   v
Sees daily menu (CMS-driven)
   |
   v
Clicks "Ordina" on a product or "Prenota una torta su misura"
   |
   v
Order form (typed: product, quantity, pickup date/time, name, email/phone)
   |
   v
POST /api/order
   |
   +--> Gmail confirmation to customer  (reuses gmail_api_send from 002)
   +--> Gmail notification to Marta     (same skill)
   +--> Calendar event on Marta's chosen calendar (reuses 007 adapter)
   +--> Plausible custom event "order_placed" (measurable conversion)
```

Drop-off points are now measurable: page view -> menu view -> form open -> form submit -> calendar event created.

### Schema gaps closed in v2

```json
{
  "@context": "https://schema.org",
  "@type": "Bakery",
  "name": "Forno di Marta",
  "image": "https://forno-di-marta.vercel.app/og.png",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "<TBD>",
    "addressLocality": "Milano",
    "addressCountry": "IT"
  },
  "telephone": "<TBD>",
  "priceRange": "€€",
  "openingHoursSpecification": [
    {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Tuesday","Wednesday","Thursday","Friday","Saturday"], "opens": "07:00", "closes": "19:30"}
  ],
  "servesCuisine": ["Italian", "Bakery"]
}
```

Three fields marked `<TBD>` — APD flags these as the only blocking content gaps for v2.

### Cross-product integration opportunities

| AI Studio product | How the bakery v2 uses it |
|---|---|
| 002 — Gmail send | Order confirmation + Marta notification (replaces Formspree) |
| 007 — Calendar sync | Order -> calendar event on Marta's Google / Apple / Outlook calendar |
| 006 — RAG | Optional future v3: chatbot on the site that answers "do you have gluten-free?" trained on Marta's menu |

### Webhook contract (one-liner per endpoint)

```
POST /api/order
  body: { product: str, quantity: int (1..50), pickup_at: ISO8601, name: str, email: str, phone?: str, notes?: str }
  200:  { order_id: str, pickup_at: ISO8601, calendar_event_url: str }
  400:  { error: "invalid_email" | "pickup_in_past" | "quantity_out_of_range" }
  429:  { error: "rate_limited", retry_after_sec: int }
  5xx:  Sentry alert fires
```

**APD block condition**: no public webhook ships without this contract written in `site/README.md`.

---

## 4. Devil's Advocate

### Unverified assumptions in v1

| Claim | Source | Status | What would verify it |
|---|---|---|---|
| "Warm colour palette" matches Marta's brand | User input, never validated against Marta | unverified | Send Marta a 30-second loom; ask. |
| Marta wants a contact form | Inferred from "I want a contact form" in the brief | unverified that *Marta* asked, not the dispenser user | Find out if the dispenser user is Marta or someone else commissioning the site for her. |
| Marta reads email regularly | Implicit | unverified | Ask. If she doesn't, the form is theatre and 007's calendar integration matters more than email. |
| "Pane e dolci artigianali dal 1987" | Hardcoded in v1's hero | unverified | Confirm the founding year before printing it on the web. |

### Hidden ops costs in the v2 plan

| v2 feature | Who runs it after we ship | Realistic failure mode |
|---|---|---|
| Decap CMS | Marta has to learn it | She doesn't open it for six months; menu is permanently "Pane fresco" |
| Order form -> Gmail | Marta reads Gmail | She doesn't; orders sit; we look bad |
| Order form -> calendar event | Marta uses one calendar consistently | She uses iCal on her phone + Google on her laptop and they get out of sync (the exact problem 007 was built to solve, but only if she actually opens both) |
| Plausible analytics | Someone looks at the dashboard | Nobody does; we paid €9/mo for nothing |
| Sentry | Someone reads error alerts | Same |
| OG images | Someone shares the link | Marta's customers are walk-ins; the OG card may never render |

### Buyer fit

The buyer paid €9.90 for "a one-page bakery website with a contact form." There's no evidence yet they want a CMS, an order pipeline, or analytics. Selling v2 means selling **another product**, not patching the first.

Two scenarios:

1. **The buyer was Marta herself**, who is digitally fluent and was bottlenecked by the v1's manual-edit problem. v2 lands well; she pays €30-40 for the upgrade.
2. **The buyer was a relative/staff member** acting on Marta's behalf, who got a website to make Marta happy. v2 is over-engineered for the actual user; she won't use the CMS; the order form will not be answered.

We do not currently know which scenario is true. The V2 Team is **designing for scenario 1**; we should price for **scenario 2**.

### Price floor (DA's number)

- **APD's recommended ceiling**: €39.90 (premium one-pager with monetisation hooks, three integrations, CMS).
- **DA's floor**: **€24.90**.
- **Reasoning for the floor**: the buyer paid €9.90 a day ago. Charging more than 2.5x for an upgrade they didn't ask for is high friction. €24.90 is roughly €15 over v1 — the size of a casual upsell, low enough that scenario-2 buyers can absorb it as "Luigi suggested this and it sounds reasonable."

If the team wants to ship at €39.90 anyway, that's a Luigi-level decision per the DA's structured veto.

### The sunset case

> "Marta's site went live yesterday. Nobody has complained. Nobody has asked for a CMS. The bakery has run for almost forty years without analytics dashboards. The v1 cost us 80 seconds of agent time and €9.90 of revenue at >95% margin. The right move is to leave it alone, watch the form for a week, and if a real complaint surfaces, fix exactly that. The V2 Team is solving a problem the buyer hasn't articulated, with features we want to build because they're interesting to us. Ship nothing."

This argument is uncomfortable. The DA endorses *some* of it: ship the **zero-ops upgrades** (JSON-LD, OG tags, Tailwind compile, fix the placeholder image, fix the `YOUR_FORM_ID` literal) for free as a courtesy / warranty pass on 001, and **gate the CMS + order flow** behind an explicit "Marta, do you actually want this?" conversation before charging her for it.

---

## Converged recommendation

The four agents converge on the following:

1. **Ship the v2 build** described in `site/` and `webhook/`.
2. **Split the SKU into two tiers** to honour both the APD's ceiling and the DA's floor:
   - `landing_page_premium` — €24.90 — fixes 001's defects, adds SEO/OG/JSON-LD/observability, compiles Tailwind, keeps Formspree.
   - `landing_page_commercial` — €39.90 — everything in `landing_page_premium` plus Decap CMS, order webhook, Gmail + calendar integration.
3. **Marco escalates both new SKUs to Luigi** per the `unknown_product:null` rule. Luigi picks the prices (the numbers above are recommendations).
4. **Free courtesy pass on 001**: the placeholder image and `YOUR_FORM_ID` literal are warranty defects from request 001 — fix them in 001's folder at no charge, regardless of whether Luigi approves v2 pricing.
5. **Send Marta the unverified-assumptions list before charging her for v2**. If she doesn't want a CMS, don't build her one.
6. **Open ISS-014** to productionise the V2 Team workflow (auto-trigger on Stacy QA defect-shipped flag) and **ISS-015** to set the two premium SKU prices.

Sign-offs:

- Quality Reliability Lead — approves on condition that Lighthouse Performance >= 70 and Sentry covers the webhook before delivery.
- Core Architect — approves on condition that the order webhook reuses 002's Gmail skill and 007's calendar adapter (no third path).
- API Product Designer — approves on condition that `site/README.md` includes the webhook contract verbatim.
- Devil's Advocate — soft-vetoes anything above the €24.90 / €39.90 split until Marta is asked which scenario applies.
