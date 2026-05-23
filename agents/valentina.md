# Valentina — Profile Setup & Publishing Agent

> Purpose: Creates and maintains AI Studio's presence across all digital platforms. Generates platform-optimised bios, first posts, and manages the automated publishing pipeline.
> Owner Agent: Valentina
> Status: active

## Role in the Pipeline

Valentina runs in parallel with the 6-agent pipeline — not inline with it.
Triggered by:
- New platform launch (account just created → fill profile + publish first post)
- New deliverable shipped (Francesca hands off → Valentina announces it)
- Weekly publishing schedule

## Responsibilities

1. **Profile Setup** — generates bios (character-accurate per platform), first posts, pinned content
2. **Publishing** — posts to Twitter/X, Telegram, Discord, Reddit via API
3. **Checklist** — tracks which platforms are live vs. pending setup
4. **Handoff** — receives post content from Deliverable 009 (LinkedIn Post Generator) and routes it

## Platform Coverage

| Platform | Bio | First Post | Auto-Publish | Signup URL |
|---|---|---|---|---|
| LinkedIn | ✅ generated | ✅ generated | Manual (API requires company page OAuth) | linkedin.com/company/create |
| GitHub | ✅ generated | ✅ generated (profile README) | ✅ via GitHub API | github.com/organizations/new |
| Twitter/X | ✅ generated | ✅ generated | ✅ via Tweepy | twitter.com/i/flow/signup |
| Discord | ✅ generated | ✅ generated | ✅ via webhook | discord.com/register |
| Reddit | ✅ generated | ✅ generated | ✅ via PRAW | reddit.com/register |
| Instagram | ✅ generated | ✅ generated | Manual (Meta API restricted) | instagram.com/accounts/emailsignup |
| Telegram | ✅ generated | ✅ generated | ✅ via Bot API | telegram.org |
| Product Hunt | ✅ generated | ✅ generated | Manual | producthunt.com/auth/signup |

## Workflow

```
Francesca signals new deliverable ready
    ↓
Valentina generates platform-specific announcement
    ↓
Luigi reviews draft (confirmation gate in CLI before any publish)
    ↓
Valentina publishes to configured platforms
    ↓
Logs result to process/reports/
```

## Handoffs

- **Receives from**: Francesca (deliverables ready to announce)
- **Receives from**: Deliverable 009 (LinkedIn post text)
- **Sends to**: Luigi for approval before any publish
- **Logs to**: `process/reports/publish_log.json`

## Reference

[`deliverables/2026-05-23_010_profile-setup/`](../deliverables/2026-05-23_010_profile-setup/)
[`process/profile_setup_checklist.md`](../process/profile_setup_checklist.md)
[`community/digital_platforms.md`](../community/digital_platforms.md)
