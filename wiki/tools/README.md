# Tools Wiki — AI Studio Accademia Milano

Every stack decision made in this studio, and why.

---

## Core Language: Python

All pipeline agents, scripts, and deliverables are Python. No exceptions unless the output is a static site.

**Why:** LangGraph, LangChain, Streamlit, fpdf2, Alpaca, Twilio SDKs — all Python-first. One language = one `requirements.txt` per deliverable, no polyglot complexity.

**Version:** 3.11+ (match Streamlit Cloud's runtime).

---

## AI Framework: LangGraph / LangChain

| Tool | Use |
|------|-----|
| `langgraph` | Multi-agent pipelines with state, cycles, and human-in-the-loop |
| `langchain` | Tool use, RAG chains, document loaders |
| `anthropic` SDK | Direct Claude API access — preferred for studio agents |
| `openai` SDK | OpenAI fallback, embeddings, structured output |

**Rule:** Use the Anthropic SDK directly when possible (prompt caching, extended thinking). Use LangChain/LangGraph when the pipeline needs memory, branching, or multi-agent coordination.

---

## UI: Streamlit

All interactive deliverables use Streamlit unless the client explicitly needs a website.

**Why:** 1 Python file = deployed app. No frontend, no React, no build step.

```python
import streamlit as st
st.title("My App")
response = st.chat_input("Ask something")
```

**Deploy:** Streamlit Cloud (free tier, GitHub-connected, auto-redeploy on push).

---

## Static Sites: HTML + Tailwind + AlpineJS

Deliverable type: `static_landing_page`, `premium_landing_page`, `commercial_landing_page`.

| Layer | Tool | Why |
|-------|------|-----|
| Markup | HTML5 | Zero build step, Vercel serves as-is |
| Styling | Tailwind CSS (CDN) | Utility-first, no config needed |
| Interactivity | AlpineJS (CDN) | Reactive without a framework |
| CMS | Decap CMS | Git-backed, no database |
| Contact forms | Formspree | Free tier, no backend |
| Deploy | Vercel | Drag-and-drop or `npx vercel`, free |

---

## Hosting Decision Tree

```
Is it a Streamlit app?
  → Streamlit Cloud (free, GitHub-connected)

Is it a static site?
  → Vercel (free, auto-SSL, global CDN)

Is it a containerised app (e.g. LangGraph with TA-Lib)?
  → HF Spaces (Docker, GPU optional) or Google Cloud Run (pay-per-request)

Is it an API / webhook?
  → Cloud Run (HTTPS endpoint, scales to zero)
```

---

## DNS & Domains

| Service | Role |
|---------|------|
| **Namecheap** | Domain registrar (`aistudiomilano.xyz`, €1.72/yr) |
| **Cloudflare** | DNS, DDoS protection, proxying — free tier |

**Rule:** All DNS managed via Cloudflare, never directly at the registrar. API token: `CLOUDFLARE_API_TOKEN` (Zone:DNS:Edit scope).

---

## Email

| Service | Role |
|---------|------|
| **Zoho Mail** | Business email `luigi@aistudiomilano.xyz` — standalone mailbox, no forwarding |
| **Gmail API** | Programmatic sending for deliverables 002, 003 and future email delivery SKU |

**Rule:** Gmail API uses OAuth2. Tokens are session-scoped and never stored to disk.

---

## Payments

| Service | Role | Status |
|---------|------|--------|
| **Stripe** | Card payments at dispenser | Pending (needs Partita IVA) |
| **Satispay** | Italian mobile payments (stub in deliverable 014) | ISS-013 |
| **PayPal** | Fallback (stub in deliverable 014) | ISS-013 |

---

## Messaging APIs

| API | Use | Credentials |
|-----|-----|-------------|
| **Twilio** | WhatsApp inbound + outbound | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` |
| **Telegram Bot API** | Telegram inbound + outbound, admin notifications | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` |

**Security:** Twilio webhooks validated with HMAC-SHA1. Telegram uses long-polling or webhook with secret token.

---

## Version Control: GitHub

| Feature | Use |
|---------|-----|
| Repo | `laceto/AIstudioAccademiaMilano` — all studio code |
| Branches | `claude/<slug>` per feature, merge to `main` |
| Actions | Digital presence pipeline (weekly cron), future: CI tests |
| Tokens | `GITHUB_TOKEN` — scope: `repo, workflow` |

---

## Claude Code Workflows

### Skills (slash commands)

Reusable prompts in `~/.claude/skills/`. Key ones for this studio:

| Skill | When to use |
|-------|-------------|
| `/git-commit` | Conventional commit with auto-staging |
| `/new-branch` | Create + push `claude/<slug>` branch |
| `/streamlit-app` | Scaffold a new Streamlit deliverable |
| `/pdf-generate` | Generate a PDF via InvoiceTemplate |
| `/update-docs` | Sync wiki and CLAUDE.md after delivery |

### Hooks (auto-triggered)

Configured in `.claude/settings.json`:

| Hook | Trigger | Action |
|------|---------|--------|
| `UserPromptSubmit` | Every prompt | RAG context injection (top-5 repo chunks) |
| `Stop` | Session end | `learning_loop.py` updates skills + settings |
| `PostToolUse` | After `mcp__github__push_files` | `learning_loop.py` delivery_complete event |
| `PreToolUse` | Gmail tool | OAuth check |

### Memory system

`C:\Users\l_ace\.claude\projects\...\memory\` — persists across sessions. Updated by `learning_loop.py`. Contains: user profile, feedback, project state, references.

---

## Credential Management

All secrets live in `.env` (gitignored) or Streamlit Secrets. Never in code.

```bash
cp .env.example .env
# fill in values
```

Full credential guide: `credentials/registry.md` — step-by-step for all 19 credentials across all deliverables.

**TTL:** OAuth tokens are session-scoped (managed by `scripts/credential_manager.py`). API keys are permanent in `.env`.

---

## Monitoring & Observability

| What | Where | How |
|------|-------|-----|
| Pipeline runs | `process/audit/YYYY-MM-DD_NNN_slug.md` | Written by Francesca after every delivery |
| Learning loop | `logs/learning_loop.log` | Appended by Stop hook |
| Skills & patterns | `config/global_settings.json` | Updated by `learning_loop.py` |
| Open issues | CLAUDE.md + `config/global_settings.json → open_issues` | Managed by Lorenzo |
