# Claude Code Development Guide

> How AI Studio Accademia Milano uses Claude Code as its primary development interface.

**Owner**: Gianni (Il Tecnico)
**Status**: active

---

## Overview

Claude Code (claude.ai/code) is the primary interface through which this AI enterprise builds, manages, and documents everything. Every service, agent, process, and document in this repo was created through Claude Code. This guide is the team reference for using it effectively.

---

## Project CLAUDE.md — Router Pattern

This project uses the **router pattern**: CLAUDE.md is a pure conditional router, not a rules manual.

```
CLAUDE.md           ← router only, loaded every session (~300 tokens)
brainstorm-rules.md ← loaded for new requests / exploration
build-rules.md      ← loaded for implementation tasks
agent-rules.md      ← loaded for creating/extending staff agents
project-setup-rules.md ← loaded for new repo creation
docs-rules.md       ← loaded for documentation tasks
```

**Rule**: Always identify task type first, then load only the matching rules file.

---

## Agent Roster (`~/.claude/agents/`)

Specialized sub-agents available in every Claude Code session:

| Agent | Invoke when |
|-------|-------------|
| `claude-code-guide` | Questions about Claude Code features, patterns, hooks, MCP, agents |
| `api-product-designer` | API ergonomics review, DX audit, naming, documentation rewrite |
| `core-architect` | Refactoring, module boundaries, technical debt, design patterns |
| `quality-reliability-lead` | Test coverage, CI/CD, regression testing, performance benchmarking |
| `devils-advocate` | Challenging a design before it ships, adversarial second opinion |
| `langgraph-pattern-upgrade` | Refactoring LangGraph agents to dynamic scalability patterns |

Agents write to files — never chat-only. Always check the actual output file, not just the agent's summary.

---

## Memory System

Project memory lives at:
```
C:\Users\l_ace\.claude\projects\C--Users-l-ace-Desktop-projects-AIstudioAccademiaMilano\memory\
```

**MEMORY.md** is the index — loaded every session. Entries must stay under 150 characters each.

Memory types used in this project:
- **project** — ongoing work, goals, phase of the 90-day roadmap
- **user** — Luigi's preferences, decision style
- **feedback** — what worked / what to never repeat
- **reference** — external systems, dashboards, links

Save memory immediately when something non-obvious is learned. Don't rely on conversation history.

---

## New Project Setup Workflow

When spinning up a new deliverable:

```bash
# 1. Create GitHub repo
gh repo create AIstudio_Project_$(date +%Y%m%d) --public

# 2. Add as submodule
git submodule add <repo-url> projects/<project-name>

# 3. Register in ProjectRegistry.md
# (create if missing — see project-setup-rules.md for format)

# 4. Scaffold initial docs
# Run: /brainstorm → save output → /docs-rules
```

---

## AI Stack Defaults

When Gianni implements new services:

| Layer | Default |
|-------|---------|
| Language | Python |
| Project config | `pyproject.toml` |
| Workflow orchestration | LangChain |
| Multi-agent graphs | LangGraph |
| Analog-to-digital solutions | DeepAgents |
| Default LLM | `claude-sonnet-4-6` |
| Complex reasoning | `claude-opus-4-7` |

---

## Parallel Agent Workflow

For independent tasks, always launch agents in parallel:

```
Main conversation
├── Agent A (background) — e.g., process docs folder
└── Agent B (background) — e.g., create new agent profile
```

Claude Code notifies when each completes. Do not poll.

Protect the main context window: spawn agents for heavy research. Pass exact file paths and findings — never make an agent rediscover what you already know.

---

## Context Management

| Threshold | Action |
|-----------|--------|
| ~70% full | Start planning to wrap up |
| ~85% full | Run `/compact` immediately |
| ~90%+ | Start new session |

For long multi-phase tasks, break into sessions. Use the memory system to carry forward decisions.

---

## Hooks (Automation Layer)

Hooks are configured in `.claude/settings.local.json` (project-level, gitignored) or `~/.claude/settings.json` (user-level).

Current hooks in this project: see `.claude/settings.local.json`.

Useful hooks to add as the enterprise grows:
- **PostToolUse(Write)** → auto-log all file writes for audit trail
- **Stop** → send notification when a session ends
- **PreToolUse(Bash)** → block destructive commands in production

---

## Brainstorm-First Enforcement

Every new user request → `brainstorm-rules.md` → `/brainstorm` skill → save `.md` → commit.

No code is written without a documented brainstorming output. This is how the enterprise learns and grows with each request.

---

## Key Claude Code Commands for This Enterprise

| Command | When to use |
|---------|-------------|
| `/brainstorm` | Every new request — mandatory first step |
| `/init` | Initializing CLAUDE.md for a new project repo |
| `shift+tab` | Plan mode — for any task spanning >3 files |
| `/compact` | Before context hits 85% |
| `! gh repo create ...` | Creating new project repos inline |
| `/code-review` | Before shipping any significant build |
| `/git-commit` | Committing with Conventional Commits format |

---

## Reference

- Full Claude Code guide: `~/.claude/agents/claude-code-guide.md`
- Source guide: https://github.com/FlorianBruniaux/claude-code-ultimate-guide (v3.40.0, May 2026)
- Risk review process: `process/risk_review_process.md`
- Delivery workflow: `process/User_Request_to_Delivery.md`
