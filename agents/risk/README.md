# AI Risk Management Department

> Purpose: 5-agent team responsible for monitoring and mitigating technical, financial, operational, reputational, and compliance risk across all AI Studio systems.
> Owner Agent: Luigi (Founder) — final decision authority
> Status: active

## Pipeline

```
Luigi (Founder Layer — final approvals)
    |
    ├── Technical Auditor     (code, security, deployments)
    ├── Financial Controller  (costs, pricing, invoices)
    ├── Operational Monitor   (uptime, automations, pipelines)
    ├── Reputation Guardian   (output quality, demos, client feedback)
    └── Compliance Agent      (data privacy, API terms, documentation)
```

## Risk Categories

| Category | Agent | Examples |
|---|---|---|
| Technical | Technical Auditor | deployment failures, hallucinations, API outages |
| Financial | Financial Controller | runaway costs, underpriced projects, unpaid invoices |
| Operational | Operational Monitor | workflow failures, broken automations, concurrent session conflicts |
| Reputational | Reputation Guardian | broken demos, low-quality outputs |
| Legal/Compliance | Compliance Agent | data privacy, terms violations |

## Agent Profiles

- [`technical_auditor.md`](technical_auditor.md)
- [`financial_controller.md`](financial_controller.md)
- [`operational_monitor.md`](operational_monitor.md)
- [`reputation_guardian.md`](reputation_guardian.md)
- [`compliance_agent.md`](compliance_agent.md)

## Mistake Log Obligation

All five risk agents are **primary contributors** to `process/mistake_log.md`. Risk agents are positioned to observe failures before anyone else — that makes logging non-optional.

- **Technical Auditor**: log every security flag, broken deploy, or architectural divergence that caused rework.
- **Financial Controller**: log every pricing block, runaway cost event, or invoice error.
- **Operational Monitor**: log every pipeline failure, missed cron, concurrent session conflict, or hook regression.
- **Reputation Guardian**: log every quality flag that reached a client or broke a demo.
- **Compliance Agent**: log every ToS violation found or data handling gap discovered.

Entries go to `process/mistake_log.md` immediately upon discovery.

## Architecture Reference

[`framework/ai_risk_management_team.md`](../../framework/ai_risk_management_team.md)
