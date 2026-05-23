# Learning Loop — From Every Request to System Improvement

Every completed user request is an opportunity to make the system faster, smarter, and more capable. This document defines how AI Studio Accademia Milano learns automatically from what it does.

---

## Overview

```
User Input
    │
    ▼
[Pipeline runs — Stacy → Gianni → Chiara → Stacy QA → Marco → Francesca]
    │
    ▼
Audit Log written  →  process/audit/YYYY-MM-DD_NNN_slug.md
    │
    ▼
Learning Script runs  →  scripts/learning_loop.py
    │
    ├── New skill detected?     → update config/global_settings.json#skills
    ├── New agent behaviour?    → update agents/ files
    ├── New hook pattern?       → update .claude/settings.json#hooks
    └── New MCP tool used?      → update config/global_settings.json#mcp
    │
    ▼
Luigi reviews diff (auto-approved if risk_score < 3)
    │
    ▼
Commit → main  ("learn: update global settings from request NNN")
```

---

## What Triggers the Learning Loop

The loop fires on two events, configured in `.claude/settings.json`:

| Event | Hook | Action |
|-------|------|--------|
| Session ends (Claude stops) | `Stop` | Run `learning_loop.py --event session_end` |
| Delivery confirmed (Francesca completes) | `PostToolUse` on push/send | Run `learning_loop.py --event delivery_complete` |

---

## What the System Learns

### 1. Skills
A **skill** is a tool, library, or technique successfully used in a request.

- First time `fpdf2` is used → added to `skills` registry with intent mapping
- First time Gmail OAuth is used → added to `skills` with dependency flag
- Next time a similar request arrives → Stacy pre-loads the known skill, skipping discovery

### 2. Agent Capabilities
Each agent's profile in `agents/README.md` is updated with:
- New task types they successfully handled
- Average time per task type
- Failure patterns (if QA failed, what was the cause)

### 3. Hooks
When a **recurring pattern** is detected across ≥ 3 requests:
- A new hook is written to `.claude/settings.json`
- Example: Gmail OAuth appears in 3+ requests → a `PreToolUse` hook is added that pre-checks OAuth token validity before Chiara starts generating

### 4. MCP Endpoints
Every external API or MCP tool used is registered in `config/global_settings.json#mcp`:
- Tool name, endpoint, auth method, average latency
- If a tool fails > 20% of the time → flagged for Gianni review

---

## Risk Scoring

Before auto-committing a settings update, the learning script scores the change:

| Change type | Risk score |
|-------------|------------|
| Add new skill (read-only tool) | 1 |
| Update agent average time | 1 |
| Add new MCP endpoint (read-only) | 2 |
| Add new hook (pre-tool check) | 2 |
| Add new MCP with write access | 4 |
| Modify existing hook logic | 4 |
| Remove a skill or hook | 5 |

- **Score < 3** → auto-approved, committed directly
- **Score 3–4** → Stacy notifies Luigi for approval before commit
- **Score ≥ 5** → blocked, requires explicit Luigi sign-off

---

## Audit Log Format

See `process/audit/README.md` for the full schema.

Each log file is named: `YYYY-MM-DD_NNN_slug.md`  
where `NNN` is a zero-padded sequential request number.

---

## Learning Script

See `scripts/learning_loop.py` for the implementation.

The script:
1. Reads the latest audit log
2. Diffs against `config/global_settings.json`
3. Proposes updates
4. Scores risk
5. Commits if auto-approved, or opens a GitHub issue for Luigi if not
