# Mindful Bot

Adaptive Telegram bot for psychologists and their patients.
Collects a user profile during onboarding and delivers personalised mindfulness
prompts + mood check-ins at each user's own wake time.

## Profiles

| Profile | Who | Prompt style | Default wake | Default check-in |
|---------|-----|-------------|-------------|-----------------|
| `adult` | Adult patients | Standard mindfulness | 08:00 | 21:00 |
| `child` | Children (or set up by a parent) | Simple, playful, short | 07:00 | 19:00 |
| `night_worker` | Shift / night workers | Sleep-hygiene focused, shifted | 16:00 | 02:00 |

## Onboarding flow (2 steps after /start)

1. **"Chi usera questo bot?"** — reply keyboard: `Per me (adulto)` / `Per un bambino` / `Lavoro di notte`
2. **"A che ora ti svegli?"** — free text hour (0-23); evening check-in auto-set to wake + 13h

Profile and times are saved per user. `/start` is idempotent for already-subscribed users.

## Commands

- `/start` — onboarding (or status if already subscribed)
- `/stop` — unsubscribe
- `/umore` or `/mood` — manual mood check-in (1-5)
- `/aiuto` or `/help` — show profile + scheduled times

## Scheduler

Runs every **30 minutes**. For each subscriber, checks whether `now.hour` matches
their personal `morning_hour` or `evening_hour` — so every user gets messages at
their own time, not a global fixed time.

## Mood adaptation

- Scores 1-5 logged to `data/mood_log.csv` with trigger (`manual` or `scheduled`)
- Last 5 scores stored per user in `subscribers.csv`
- If the last 3 scores are all <= 2: a professional support suggestion is appended to the reply

## Local setup

```bash
cd deliverables/2026-05-25_017_mindful-bot
cp .env.example .env          # set TELEGRAM_BOT_TOKEN
pip install -r requirements.txt
python bot.py
```

## Railway deploy

1. Connect repo to Railway.
2. Set `TELEGRAM_BOT_TOKEN` in the env vars panel.
3. Railway detects `Procfile` and runs the bot as a Worker.

## Data files (git-ignored)

| File | Columns |
|------|---------|
| `data/subscribers.csv` | `chat_id, username, subscribed_at, profile, morning_hour, evening_hour, onboarding_step, recent_moods, prompt_index` |
| `data/mood_log.csv` | `timestamp, chat_id, username, score, trigger` |
