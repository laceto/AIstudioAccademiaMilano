# Deliverable 010 — Profile Setup & Publishing Agent (Valentina)

> Purpose: Generates platform-optimised bios and first posts for all AI Studio channels, then publishes to platforms with configured credentials.
> Owner Agent: Valentina
> Status: active

## Credentials Required

| Credential | Required for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | **All generation** | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `TWITTER_API_KEY` + `TWITTER_API_SECRET` + `TWITTER_ACCESS_TOKEN` + `TWITTER_ACCESS_SECRET` | Twitter/X publish | [developer.twitter.com](https://developer.twitter.com) → Projects → Keys & Tokens |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHANNEL_ID` | Telegram publish | @BotFather on Telegram |
| `DISCORD_WEBHOOK_URL` | Discord publish | Server Settings → Integrations → Webhooks |
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` + `REDDIT_USERNAME` + `REDDIT_PASSWORD` | Reddit publish | [reddit.com/prefs/apps](https://reddit.com/prefs/apps) → create app (script type) |

LinkedIn, Instagram, Product Hunt: **manual posting** (API OAuth too complex for first post). Tool generates the text; you paste it.

---

## Setup

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# Add publishing credentials as needed (see table above)
pip install -r requirements.txt
```

---

## Run

### See all platforms and their publish method
```bash
python main.py --list
```

### Generate everything (all bios + all first posts)
```bash
python main.py --generate
```

### Generate for one platform only
```bash
python main.py --generate --platform twitter_x
python main.py --generate --platform linkedin
python main.py --generate --platform github_profile_readme
```

### Publish to a platform (confirmation gate before sending)
```bash
python main.py --publish telegram
python main.py --publish twitter_x
python main.py --publish discord
```

### Manual platforms — get the text + instructions
```bash
python main.py --publish linkedin
python main.py --publish instagram
```

---

## Output

All generated content saved to `output/`:

| File | Contents |
|---|---|
| `output/bios.md` | All bios in markdown with char count |
| `output/bios.json` | Same, machine-readable |
| `output/first_posts.md` | All first posts in markdown |
| `output/first_posts.json` | Same, machine-readable |
| `output/publish_log.json` | Log of published posts (created on first publish) |

---

## Platforms covered

### Bio generation (8 platforms)
`linkedin_headline`, `linkedin_about`, `twitter_x`, `github`, `instagram`, `discord_server`, `reddit`, `product_hunt`, `telegram`

### First post generation (9 formats)
`linkedin`, `twitter_x`, `twitter_x_intro_thread`, `github_profile_readme`, `discord_welcome`, `reddit_intro`, `instagram_first`, `telegram_pinned`, `product_hunt_maker`

### Auto-publish (4 platforms)
`twitter_x`, `telegram`, `discord`, `reddit`

### Manual (Luigi pastes the generated text)
`linkedin`, `instagram`, `product_hunt`, `github_profile_readme`

---

## Luigi's voice rules (enforced in system prompt)

- Never: "excited to announce", "passionate about", "leverage", "ecosystem", "game-changer"
- Specific: mentions real deliverables built
- Platform-native: each output feels natural on its platform
- Direct, first-person, builder identity
