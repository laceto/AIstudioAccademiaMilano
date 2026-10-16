---
request_id: "040"
date: "2026-10-16"
intent: internal_tooling
product_type: studio_pipeline_v2
outcome: partial
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Claude
    role: orchestrator
    action: >
      Mapped the 24 roles against the LangGraph pipeline, proposed where each belongs, got Luigi's go
      (v2 beside v1), wrote 22 tests first, then the v2 graph (Lorenzo, Devil's Advocate, Financial Controller,
      IT Staff, three more reviewers, Core Architect, Valentina), a stricter risk aggregator, and the
      PIPELINE_VERSION switch in gateway/studio_runner.py.
    duration_sec: 0
    status: ok
skills_used: [breakdown, agentic-router, langgraph-fundamentals, langgraph-dynamic-parallelism, deep-agents-core, deep-agents-orchestration]
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 2
---

Outcome is partial on purpose: offline tests pass (56 new; the suite's 13 other failures are identical on main),
but v2 has not run against a real model or the real GitHub API, and the default stays v1.
Follow-up (research digest): a weekly Scout/Analyst/Curator run (no LLM) saves a digest (gateway/research_digest.py,
POST /research/run on the worker, Firestore research/latest) that v2's Gianni reads as untrusted reference text;
missing or >14-day-old digest = Gianni scopes as before. Dockerfile.worker now also copies the v2 folder and
scripts/github_research (v2 was missing from the image) and requirements.worker.txt gained requests.
Not done: the Cloud Scheduler job itself (command in process/runbook_research_digest.md) and a worker-timeout review for v2.
Risk: more LLM calls per job (about 7 fast calls instead of 3); Lorenzo fails closed, so a scanner outage
blocks requests while v2 is on. Thresholds in nodes.py are assumptions to calibrate.
