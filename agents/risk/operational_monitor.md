# Agent 3 — Operational Monitor

> Purpose: Monitors uptime, automation health, failed jobs, and pipeline status across all running AI Studio systems.
> Owner Agent: Operational Monitor
> Status: active

## Responsibilities

- Workflow health monitoring
- Automation pipeline status checks
- Dependency health checks
- Deployment bottleneck detection

## Checks

| Area | Signal | Action |
|---|---|---|
| GitHub Actions | Failed workflow runs | Alert + retry log |
| Scripts | Uncaught exceptions in logs | Incident report |
| APIs | Rate limit exceeded, 5xx responses | Exponential backoff + alert |
| Cron jobs | Missed scheduled runs | Re-trigger + investigate root cause |

## Monitored Systems

- `.github/workflows/research_schedule.yml` — daily S-tier alert + weekly digest
- `scripts/github_research/` — research pipeline jobs
- `deliverables/2026-05-23_002_pdf-email/main.py` — email delivery
- `deliverables/2026-05-23_007_calendar-sync/` — calendar sync

## Outputs

- Job status logs → `process/reports/`
- Repeated failure (3+) → escalation to Luigi
