---
request_id: "044"
date: "2026-10-16"
intent: internal_tooling
product_type: internal
outcome: success
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: >
      "What is google-research/harness2 and how do we benefit" -> research, then Luigi chose
      "skip the demo, apply the idea": internal tooling on the learning loop, 0.00 (internal).
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      Read the harness2 demo source (cli/demo.py, demo.py): Propose -> Probe -> Compose, then an
      "experience" entry cue/lesson/evidence/confidence carried to later tasks. Mapped it onto the
      studio: learning_flags.lessons in the audit log, merged by learning_loop.py, digest read by
      Gianni and Chiara. Running the demo was blocked by the session's permission mode (external code).
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      Tests first (13), then update_lessons + write_lessons_md in scripts/learning_loop.py; digest
      process/lessons_learned.md added to the auto-commit list; docs in CLAUDE.md, process/audit/README.md,
      francesca.md; read step in gianni.md and chiara.md.
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa
    action: "54 learning loop tests pass (13 new). No network, no secrets, no new dependency."
    duration_sec: 0
    status: ok
  - name: Marco
    role: finance
    action: "Internal tooling: 0.00, no invoice."
    duration_sec: 0
    status: ok
skills_used: []
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 1
  lessons:
    - agent: Chiara
      cue: "When a deliverable needs ML model or wheel downloads (pytorch index, Hugging Face)"
      lesson: "Test against a fake embedder offline and state in the audit that the real model was not run; the build container's network blocks those hosts."
      evidence: "043: pytorch index and Hugging Face blocked by the build container network; 27 tests ran on a fake embedder."
      confidence: high
    - agent: studio
      cue: "When asked to evaluate an external GitHub repository"
      lesson: "Read its entrypoint source and explain what it does; running cloned code needs Luigi's explicit permission in the session first."
      evidence: "044: harness2-demo install and run was denied by auto mode (external code); reading cli/demo.py and demo.py was enough to explain the demo."
      confidence: high
---

Source of the idea: [google-research/harness2](https://github.com/google-research/harness2) (Apache 2.0).
No code copied: only the cue / lesson / evidence / confidence format of its "experience" entries.
Not done: the demo itself was never run here.
