# AI Studio Discord Bot

Interactive Discord bot: AI chat, slash commands, and delivery announcements.

## Credentials

| Variable | Where to get it | Required |
|---|---|---|
| `DISCORD_BOT_TOKEN` | [discord.com/developers/applications](https://discord.com/developers/applications) → Bot → Reset Token | Yes (for bot) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) | Yes (for /ask + @mention) |
| `OPENWEATHERMAP_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) — free tier | Yes (for /weather) |
| `DISCORD_WEBHOOK_URL` | Server Settings → Integrations → Webhooks → New Webhook | Yes (for announcer only) |

## Bot setup (one-time)

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**
2. **Bot** tab → **Reset Token** → copy `DISCORD_BOT_TOKEN`
3. **Bot** tab → enable **Message Content Intent**
4. **OAuth2 → URL Generator** → scopes: `bot`, `applications.commands`
5. Permissions: `Send Messages`, `Read Messages/View Channels`, `Use Slash Commands`
6. Open the generated URL → invite bot to your server

## Run

```bash
pip install -r requirements.txt

export DISCORD_BOT_TOKEN=your_token
export ANTHROPIC_API_KEY=your_key
export OPENWEATHERMAP_API_KEY=your_key
export DISCORD_WEBHOOK_URL=your_webhook_url  # optional, for announcer

python bot.py
```

## Features

### AI chat
Mention the bot or send a DM — it replies using Claude claude-sonnet-4-6 with the AI Studio persona.

### Slash commands
| Command | What it does |
|---|---|
| `/ask <question>` | Claude-powered answer in AI Studio persona |
| `/weather` | Current weather in Milan |
| `/latest` | Most recent deliverable shipped |
| `/deliverables` | Full list of all deliverables |
| `/help` | Show all commands |

### Announcer (no bot needed)
Post to Discord from any script without running the bot:

```python
from announcer import announce, announce_deliverable

announce("🚀 New post is live!")
announce_deliverable("012", "Discord Bot", "€19.90", "2026-05-24")
```

Or from CLI:
```bash
python announcer.py "Hello from AI Studio!"
```

## Files

| File | Purpose |
|---|---|
| `bot.py` | Entry point — events, @mention AI chat |
| `commands.py` | Slash commands |
| `ai_chat.py` | Claude integration |
| `announcer.py` | Webhook-based posting (no bot process needed) |
