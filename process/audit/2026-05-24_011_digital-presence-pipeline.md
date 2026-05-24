---
request_id: "011"
date: "2026-05-24"
intent: digital_presence_automation
outcome: success
agents_invoked:
  - name: Stacy
    role: Intent classification
    action: Mapped to automation bridge (D009 + D010 integration)
    duration_sec: 2
    status: ok
  - name: Gianni
    role: Technical scoping
    action: Chose sys.path bridge + GitHub Actions cron
    duration_sec: 3
    status: ok
  - name: Chiara
    role: Implementation
    action: Wrote scripts/digital_presence_pipeline.py + digital_presence.yml
    duration_sec: 120
    status: ok
  - name: Stacy QA
    role: Output validation
    action: Verified no API keys in code, env vars used throughout
    duration_sec: 5
    status: ok
  - name: Marco
    role: Financial
    action: Internal infrastructure — no client billing
    duration_sec: 1
    status: ok
  - name: Francesca
    role: Delivery
    action: Committed to claude/digital-presence-pipeline
    duration_sec: 10
    status: ok
skills_used:
  - github_actions_cron
  - sys_path_bridge
  - multi_platform_publisher
learning_flags:
  new_skills:
    - digital_presence_pipeline
    - cross_deliverable_bridge
  new_mcp: []
  risk_score: 1
---

# Digital Presence Pipeline — Build Log

## What was built

**`scripts/digital_presence_pipeline.py`** — bridge script that:
- Imports D009 modules (`github_reader`, `post_generator`) and D010 modules (`publisher`) via `sys.path`
- Generates a LinkedIn post from recent GitHub activity
- Auto-publishes to Telegram, Twitter/X, Discord (or any configured subset)
- Saves the post to `process/digital-presence/YYYY-MM-DD_linkedin_post.txt`
- Logs every run to `process/digital-presence/run_log.json`

**`.github/workflows/digital_presence.yml`** — GitHub Actions cron:
- Fires every Monday 09:00 UTC
- Also triggerable manually via `workflow_dispatch` with custom days/platforms/dry-run inputs
- Commits generated post back to repo
- Uploads post as a downloadable artifact (30-day retention)

## Credentials required (GitHub Secrets)

| Secret | Required | Platform |
|--------|----------|----------|
| `ANTHROPIC_API_KEY` | Yes | Post generation |
| `TELEGRAM_BOT_TOKEN` | If using Telegram | Auto-publish |
| `TELEGRAM_CHANNEL_ID` | If using Telegram | Auto-publish |
| `TWITTER_API_KEY` + 3 more | If using Twitter/X | Auto-publish |
| `DISCORD_WEBHOOK_URL` | If using Discord | Auto-publish |

LinkedIn is always manual — paste from the artifact or `process/digital-presence/`.
