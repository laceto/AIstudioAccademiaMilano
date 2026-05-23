# Platform Profile Setup Checklist

> Purpose: Step-by-step checklist for creating and completing AI Studio's presence on each platform.
> Owner Agent: Valentina
> Status: active

Generate bios and first posts first:
```bash
cd deliverables/2026-05-23_010_profile-setup
python main.py --generate
# All content saved to output/bios.md and output/first_posts.md
```

---

## GitHub

- [ ] Create organisation: [github.com/organizations/new](https://github.com/organizations/new)
  - Name: `AIStudioAccademiaMilano`
  - Plan: Free
- [ ] Set org bio from `output/bios.md` → `github` section
- [ ] Upload avatar (logo)
- [ ] Create profile README repo: `<org>/<org>`, add `output/first_posts.md` → `github_profile_readme` section
- [ ] Pin key repos: hello-world, deliverables
- **Auto-publish**: N/A (manual repo setup)

---

## LinkedIn

- [ ] Create company page: [linkedin.com/company/create](https://www.linkedin.com/company/create)
  - Name: `AI Studio Accademia Milano`
  - Industry: Software Development
  - Size: 1-10
- [ ] Headline: paste from `output/bios.md` → `linkedin_headline`
- [ ] About: paste from `output/bios.md` → `linkedin_about`
- [ ] Upload logo + banner
- [ ] First post: paste from `output/first_posts.md` → `linkedin`
- **Auto-publish**: Manual (use Deliverable 009 for ongoing posts)

---

## Twitter / X

- [ ] Create account: [twitter.com/i/flow/signup](https://twitter.com/i/flow/signup)
  - Handle: `@AIStudioMilano` (or closest available)
- [ ] Bio: paste from `output/bios.md` → `twitter_x` (160 chars max)
- [ ] Upload avatar + banner
- [ ] Get API keys: [developer.twitter.com](https://developer.twitter.com) → Projects & Apps → Keys and tokens
  - Set: `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET`
- [ ] First tweet:
  ```bash
  python main.py --generate --platform twitter_x
  python main.py --publish twitter_x
  ```
- [ ] Intro thread:
  ```bash
  python main.py --generate --platform twitter_x_intro_thread
  # Copy from output/first_posts.md and post as thread manually
  ```

---

## Discord

- [ ] Create server: [discord.com/channels/@me](https://discord.com/channels/@me) → ➕ Add a Server
  - Name: `AI Studio Accademia Milano`
  - Template: Community
- [ ] Set server description from `output/bios.md` → `discord_server`
- [ ] Create channels: `#welcome`, `#builds`, `#ideas`, `#general`, `#jobs`
- [ ] Create webhook: Server Settings → Integrations → Webhooks → New Webhook
  - Set: `DISCORD_WEBHOOK_URL`
- [ ] Post welcome message:
  ```bash
  python main.py --generate --platform discord_welcome
  python main.py --publish discord
  ```

---

## Reddit

- [ ] Create account: [reddit.com/register](https://reddit.com/register)
  - Username: `u/AIStudioMilano`
- [ ] Bio: paste from `output/bios.md` → `reddit`
- [ ] Create app (for API): [reddit.com/prefs/apps](https://reddit.com/prefs/apps) → create app
  - Type: **script**
  - Redirect URI: `http://localhost:8080`
  - Set: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`
- [ ] First post (choose subreddit):
  ```bash
  python main.py --generate --platform reddit_intro
  python main.py --publish reddit
  # Will ask for subreddit name at prompt
  ```

---

## Instagram

- [ ] Create account: [instagram.com/accounts/emailsignup](https://www.instagram.com/accounts/emailsignup)
  - Handle: `@aistudio.milano` (or closest available)
  - Account type: Creator or Business
- [ ] Bio: paste from `output/bios.md` → `instagram` (150 chars max)
- [ ] Upload profile photo
- [ ] First post: paste caption from `output/first_posts.md` → `instagram_first` + add workspace photo
- **Auto-publish**: Manual (Meta API restricted for new accounts)

---

## Telegram

- [ ] Create channel via Telegram app: New Channel
  - Name: `AI Studio Accademia Milano`
  - Type: Public
  - Username: `@AIStudioMilano`
- [ ] Create bot via @BotFather: `/newbot`
  - Add bot as admin to the channel
  - Set: `TELEGRAM_BOT_TOKEN`
  - Set: `TELEGRAM_CHANNEL_ID` = `@AIStudioMilano`
- [ ] Post pinned welcome:
  ```bash
  python main.py --generate --platform telegram_pinned
  python main.py --publish telegram
  ```

---

## Product Hunt

- [ ] Create maker account: [producthunt.com/auth/signup](https://www.producthunt.com/auth/signup)
- [ ] Maker profile: paste from `output/first_posts.md` → `product_hunt_maker`
- [ ] Upload avatar
- [ ] Follow relevant makers and products
- **Auto-publish**: Manual (post launches at producthunt.com/posts/new)

---

## Status Tracker

| Platform | Account | Bio | First Post | API Set Up |
|---|---|---|---|---|
| GitHub | ⬜ | ⬜ | ⬜ | ✅ (MCP) |
| LinkedIn | ⬜ | ⬜ | ⬜ | ➖ manual |
| Twitter/X | ⬜ | ⬜ | ⬜ | ⬜ |
| Discord | ⬜ | ⬜ | ⬜ | ⬜ |
| Reddit | ⬜ | ⬜ | ⬜ | ⬜ |
| Instagram | ⬜ | ⬜ | ⬜ | ➖ manual |
| Telegram | ⬜ | ⬜ | ⬜ | ⬜ |
| Product Hunt | ⬜ | ⬜ | ⬜ | ➖ manual |

Update this table as each platform goes live.
