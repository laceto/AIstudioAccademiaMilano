---
request_id: "009"
date: "2026-05-24"
product: mindful-pause-bot
price: 19.90
---

# Risk Gate — Mindful Pause Bot

## Technical Auditor
- **No user data stored beyond trigger/choice/reflection text** — SQLite local file, no PII beyond Telegram user_id (integer)
- **No secrets in code** — all keys via `.env` / environment variables
- **Error handling** on every LLM call — fallback messages prevent silent failures
- Status: ✅ PASS

## Financial Controller
- Billed as `chatbot_app` → €19.90
- LLM cost per session: ~1200 tokens (4 Claude calls × ~300 tokens) = ~€0.003/session
- Margin: healthy at any reasonable usage volume
- Status: ✅ PASS

## Operational Monitor
- Bot requires two external services: Telegram API + Anthropic API
- Both have high uptime SLAs; no internal automation chains
- `run_polling` mode — no webhook infrastructure needed for demo/pilot
- Status: ✅ PASS

## Reputation Guardian
- Psychologist team reviews prompts before deployment — clinical framing is their IP
- Bot explicitly positions itself as a pause coach, not therapy
- No crisis intervention capability — must be communicated to end users
- Status: ✅ PASS (with caveat: add explicit disclaimer to /start message before production)

## Compliance Agent
- Telegram Bot API ToS: compliant (no spam, no unsolicited messages)
- Anthropic API ToS: compliant (user-initiated sessions, no harmful content)
- GDPR: Telegram user_id stored — add data deletion command (`/delete_my_data`) before production rollout in EU
- Status: ⚠️ CONDITIONAL — add `/delete_my_data` before EU production

## Open Risks

| Risk | Rating | Action |
|------|--------|--------|
| No crisis safeguard | High | Add `/start` disclaimer + `/crisis` command pointing to emergency resources |
| GDPR data deletion | Medium | Implement `/delete_my_data` before EU launch |
| LLM generates clinical-sounding advice | Medium | Psychologist team review prompt library before go-live |
