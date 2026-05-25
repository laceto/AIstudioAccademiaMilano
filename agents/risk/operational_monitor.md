# Agent 3 — Operational Monitor

> Purpose: Monitors uptime, automation health, failed jobs, pipeline status, and concurrent session integrity across all running AI Studio systems.
> Owner Agent: Operational Monitor
> Status: active

## Responsibilities

- Workflow health monitoring
- Automation pipeline status checks
- Dependency health checks
- Deployment bottleneck detection
- **Concurrent Claude Code session tracking** — enforces single-session-per-branch rule

## Checks

| Area | Signal | Action |
|---|---|---|
| GitHub Actions | Failed workflow runs | Alert + retry log |
| Scripts | Uncaught exceptions in logs | Incident report |
| APIs | Rate limit exceeded, 5xx responses | Exponential backoff + alert |
| Cron jobs | Missed scheduled runs | Re-trigger + investigate root cause |
| Claude Code sessions | > 1 session active on same branch | Alert Luigi; block Stop hooks until resolved |
| `global_settings.json` | File modified within < 60s of previous write | Corruption risk — alert Luigi immediately |
| Audit log IDs | Duplicate NNN in `process/audit/` | De-duplicate; escalate if content diverges |
| FAISS index | Concurrent write detected | Abort second writer; queue re-index |

## Session Concurrency Rules

**Max 1 Claude Code session per branch at any time.**

Risks when this rule is violated (actuarial formula: `P(event) × impact × blast_radius`):

| Risk | P | Impact | Blast Radius | RU |
|---|---|---|---|---|
| `global_settings.json` concurrent write → corruption | 0.7 | 3h recovery | repo-wide | **2.1** |
| Audit log NNN collision (stub created twice) | 0.5 | 0.5h recovery | single audit | 0.25 |
| `learning_loop.py` triggered twice at Stop | 0.6 | 1h recovery | settings + skills | 0.6 |
| FAISS index file lock contention | 0.3 | 0.5h recovery | RAG pipeline | 0.15 |
| Parallel git pushes to same branch → conflict | 0.4 | 1h recovery | branch | 0.4 |

**Flag threshold: RU ≥ 2.0 → escalate to Luigi immediately.**  
`global_settings.json` concurrent write breaches this threshold alone.

## Detection (Manual — No Automated Registry Today)

Claude Code has no built-in session registry. Until one exists, the Operational Monitor applies these heuristics at the start of each session:

1. Check `git log --since="5 minutes ago"` — if commits appear from another session, stop and alert Luigi.
2. Check `process/audit/` for a stub created in the last 5 minutes — if found, verify it matches current session.
3. Check `config/global_settings.json` mtime — if modified in the last 2 minutes and this session hasn't written it yet, treat as concurrent write risk.

**Recommended immediate action when multiple sessions are detected:**  
Close all sessions except one. Finish in-flight work. Reopen only when the branch is clean.

## Monitored Systems

- `.github/workflows/research_schedule.yml` — daily S-tier alert + weekly digest
- `scripts/github_research/` — research pipeline jobs
- `deliverables/2026-05-23_002_pdf-email/main.py` — email delivery
- `deliverables/2026-05-23_007_calendar-sync/` — calendar sync
- `config/global_settings.json` — settings file; corruption-risk write window monitored
- `process/audit/` — audit log ID uniqueness
- `scripts/learning_loop.py` — Stop hook; must not run concurrently

## Outputs

- Job status logs → `process/reports/`
- Repeated failure (3+) → escalation to Luigi
- Session concurrency violation → immediate escalation to Luigi (RU ≥ 2.0)
