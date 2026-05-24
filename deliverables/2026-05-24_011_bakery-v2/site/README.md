# Forno di Marta — Site v2

> v2 of deliverable 001. Premium one-pager with monetisation hooks.
> Built by the V2 Team (`agents/v2_team/`) on 2026-05-24 against request 011.

## What's in this folder

| Path | Purpose |
|---|---|
| `index.html` | Single-page site. Semantic HTML5, JSON-LD `Bakery`, OG/Twitter cards, accessible form. |
| `admin/index.html` + `admin/config.yml` | Decap CMS shell + collection config for menu and business info. |
| `content/menu/*.md` | CMS-managed menu items (sample seeded). |
| `content/business.yml` | CMS-managed business metadata (address, phone, hours). |
| `assets/bakery-placeholder.svg` | Honest placeholder image (no more `bakery.jpg`). |
| `og.svg` | OG/Twitter card source. Convert to `og.png` at build time. |
| `robots.txt`, `sitemap.xml` | Crawler hygiene. |

## Webhook contract — POST /api/order

> Verbatim per the API Product Designer's block condition in `critique_of_001.md`.

```
POST /api/order
Content-Type: application/json

Request body:
{
  "product":    string  (required, must match a current menu item title),
  "quantity":   int     (required, 1..50),
  "pickup_at":  string  (required, ISO8601, must be at least 24h in the future),
  "name":       string  (required),
  "email":      string  (required, RFC 5322),
  "phone":      string  (optional, E.164),
  "notes":      string  (optional, max 1000 chars)
}

Responses:
  200 OK     -> { "order_id": "ORD-2026-0001", "pickup_at": "...", "calendar_event_url": "..." }
  400 BadRequest -> { "error": "invalid_email" | "pickup_in_past" | "pickup_too_soon"
                              | "quantity_out_of_range" | "missing_field:<name>" | "notes_too_long" }
  429 TooManyRequests -> { "error": "rate_limited", "retry_after_sec": int }
  5xx -> Sentry alert fires; client retries after exponential backoff.

Side effects on 200:
  1. Gmail confirmation sent to `email`           (uses gmail_api_send from deliverable 002)
  2. Gmail notification sent to Marta             (same skill)
  3. Calendar event created on Marta's calendar   (uses google_calendar_api from deliverable 007)
  4. Audit row written to process/orders.log      (one line per order)
  5. Plausible event "order_placed" recorded      (if Plausible enabled)
```

Implementation lives in `../webhook/order_handler.py`.

## Deploy

```bash
# Static site
cd deliverables/2026-05-24_011_bakery-v2/site
vercel --prod                                   # reuses skill from request 001

# Order webhook (one of):
#   - Vercel Functions: drop order_handler.py under /api/ in a vercel project
#   - Google Cloud Run: reuse the deploy.sh pattern from request 010
gcloud run deploy bakery-order-api --source ../webhook --region europe-west1
```

## Secrets required (set in Vercel/Cloud Run environment)

| Secret | Where it comes from |
|---|---|
| `GMAIL_OAUTH_TOKEN_PATH` | per skill from request 002 |
| `GOOGLE_CALENDAR_ID` | Marta's calendar; per request 007 |
| `MARTA_NOTIFY_EMAIL` | Marta's inbox |
| `SENTRY_DSN` | optional — fill to enable error tracking |

## Open questions for Marta (see Devil's Advocate section of critique)

1. Did you want a contact form, or are walk-in customers your normal channel?
2. Will you actually use the CMS, or do you prefer to email Luigi when the menu changes?
3. Which calendar (Google / Apple / Outlook) do you actually open every morning?
4. Is "Dal 1987" correct?

Until 1-4 are answered, the v2 ships with TBD markers visible to Marta only.
