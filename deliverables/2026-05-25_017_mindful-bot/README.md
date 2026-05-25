# Mindful Bot

A Telegram bot for psychologists and their patients. It delivers daily mindfulness prompts and collects evening mood check-ins, logging scores to CSV for later review.

## What it does

- `/start` — Subscribe to daily prompts (saved to `data/subscribers.csv`)
- `/stop` — Unsubscribe at any time
- `/mood` — Manual mood check-in (score 1–5)
- `/help` — List all commands

Scheduled jobs (Italy time, `Europe/Rome`):
- **08:00** — Mindfulness prompt from a rotating list of 10 Italian exercises
- **20:00** — Evening mood check-in request (score logged to `data/mood_log.csv` with trigger `scheduled`)

If a user blocks the bot, they are silently removed from the subscriber list.

## Local setup

```bash
git clone <repo>
cd deliverables/2026-05-25_017_mindful-bot

cp .env.example .env
# Edit .env and set your TELEGRAM_BOT_TOKEN

pip install -r requirements.txt
python bot.py
```

## Railway deploy

1. Connect your GitHub repo to Railway.
2. Set `TELEGRAM_BOT_TOKEN` in the Railway environment variables panel.
3. Railway will detect the `Procfile` and deploy the bot as a **Worker** (no port binding needed).

## Data files (git-ignored)

| File | Content |
|------|---------|
| `data/subscribers.csv` | `chat_id, username, subscribed_at` |
| `data/mood_log.csv` | `timestamp, chat_id, username, score, trigger` |
| `data/prompt_index.json` | Current prompt rotation index (persisted across restarts) |
