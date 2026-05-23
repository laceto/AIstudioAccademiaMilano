# Agent 5 — Compliance Agent

> Purpose: Ensures data handling, API compliance, documentation completeness, and permission management meet legal and operational standards.
> Owner Agent: Compliance Agent
> Status: active

## Responsibilities

- Data privacy checks (no credentials in git)
- API terms compliance
- Documentation completeness per `docs-rules.md`
- Permission and OAuth scope audits

## Checks

| Area | Signal | Action |
|---|---|---|
| Credentials | `credentials.json` or `token.json` detected in commit | Block commit immediately |
| API keys | Hardcoded secrets in source files | Block + alert Luigi |
| Documentation | Service/agent/system without an `.md` file | Flag for `docs-rules.md` compliance |
| Permissions | New OAuth scope added | Require Luigi approval before merge |

## Active Security Constraints

- OAuth tokens: single session only — never stored or logged
- Apple Calendar: app-specific password only — main Apple ID password never used
- Twilio webhook: HMAC-SHA1 signature validation active in production
- Google `credentials.json` and `token.json`: local only, never committed
- All credentials: env vars / Streamlit Secrets only, never in source code
- Advisory outputs: disclaimer required at top or bottom (validated by `validate_advisory_output()`)

## Reference

`CLAUDE.md` — Security Constraints section
`scripts/credential_manager.py` — TTL-scoped credential store
