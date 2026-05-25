# AI Studio Master Bot

One Telegram bot, two modes: mindfulness prompts for patients and SOAP note generation for psychologists.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Subscribe to daily mindfulness reminders |
| `/stop` | Unsubscribe from reminders |
| `/mood` | Log your mood manually (1-5 scale) |
| `/soap` | Generate a SOAP note from free-text session notes |
| `/annulla` | Cancel the current operation |
| `/help` | Show available commands |

Scheduled jobs (Italian timezone):
- 08:00 — Morning mindfulness prompt sent to all subscribers
- 20:00 — Evening mood check-in sent to all subscribers

## Setup

Two environment variables required:

| Variable | Required | Purpose |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Always | Bot token from @BotFather |
| `OPENAI_API_KEY` | Only for /soap | OpenAI API key — mindfulness works without it |

```bash
cp .env.example .env
# Edit .env and fill in your values
pip install -r requirements.txt
python bot.py
```

## Railway Deploy

1. Create a new Railway project and connect this folder
2. Set service type to **Worker** (not Web)
3. Add both environment variables in the Railway dashboard under Variables
4. Deploy — Railway will run `python bot.py` via the Procfile

Note: `OPENAI_API_KEY` is optional. If not set, the `/soap` command replies with a configuration error instead of crashing. All mindfulness features remain fully functional.
