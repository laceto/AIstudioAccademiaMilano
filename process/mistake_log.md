# Studio Mistake Log & Learning Bulletin

> Living document. Every agent, staff member, and team is required to append an entry the moment a mistake is discovered — no matter how small.  
> Owner: all agents (joint). Reviewed weekly by Luigi.  
> Format: newest entry at the top.

---

## How to Add an Entry

Any agent discovering a mistake appends a new block at the **top** of the log (below this header section) using the template below. Do not wait for a retrospective — log it immediately.

```markdown
## ML-NNN — [Short title]

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Discovered by | Agent / Person name |
| Phase | Where in the pipeline it occurred |
| Impact | What broke or was affected |
| Root cause | Why it happened |
| Fix applied | What was changed to resolve it |
| Rule added | New protocol, spec change, or ISS opened |
| RU score | P × impact × blast_radius |
```

---

## ML-001 — Concurrent sessions bundled risk changes into wrong commit

| Field | Value |
|---|---|
| Date | 2026-05-25 |
| Discovered by | Operational Monitor (surfaced by Luigi) |
| Phase | Delivery / git history |
| Impact | `agents/risk/operational_monitor.md` and `agents/risk/README.md` changes landed inside `feat(brand): brand config system...` commit instead of a clean, scoped `docs(risk)` commit. Git history became misleading. |
| Root cause | Multiple Claude Code sessions were open simultaneously on `main`. A rebase in one session picked up uncommitted edits from a second session before they could be committed independently. No session registry existed to detect or prevent this. |
| Fix applied | Operational Monitor spec extended with Session Concurrency Rules: RU table, 3 detection heuristics, max-1-session-per-branch rule, and a 2.0 RU escalation threshold on `global_settings.json` concurrent writes. |
| Rule added | `agents/risk/operational_monitor.md` § Session Concurrency Rules. Standing rule: close all sessions except one before any work that touches shared files. ISS-022 opened to build automated session registry. |
| RU score | 2.1 (global_settings.json concurrent write alone exceeds the 2.0 flag threshold) |

**Lesson:** The first mistake we documented was the one that taught us we needed this document. The Operational Monitor risk spec patch was correct, but was delivered imperfectly — bundled into an unrelated commit — because we were operating in the exact condition we were trying to protect against. Meta-lesson: fix the environment before fixing the spec.

---

*This log is a studio asset, not a blame register. Entries describe systems, not people. The goal is pattern recognition — if the same root cause appears in three entries, that root cause becomes a P1 issue.*
