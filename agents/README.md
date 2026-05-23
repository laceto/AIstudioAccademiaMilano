# Agents

This folder contains profiles and roles for all AI agents operating within AI Studio Accademia Milano. Agents divide into four groups: **Staff Agents** (6-step delivery pipeline), **Valentina** (profile setup & publishing), **Risk Agents** (actuarial oversight), and the **Research Department** (GitHub AI discovery).

---

## Staff Agents — Delivery Pipeline

Every user request flows through these six agents in sequence. No step is skipped.

### Luigi (Il Fondatore)
Role: Founder and final authority.
Responsibilities:
- Sets strategy, pricing, and product direction.
- Final approval on unknown product types (`unknown_product: null`) and risk escalations.
- Only person who can override Marco's pricing block or approve real-money trading.

### Stacy (Input-Orchestrator + QA-Agent)
Role: First and fourth step in the pipeline.
Responsibilities:
- **Step 1 (Input):** Detects input type (text/voice/QR), classifies intent, extracts key entities, checks OAuth/API dependencies, routes to Gianni.
- **Step 4 (QA):** Validates Chiara's output against user specs. Runs format, security, disclaimer, and completeness checks. Blocks delivery if QA fails.

### Gianni (Request-Analyzer)
Role: Technical scoping — step 2.
Responsibilities:
- Decomposes the user request into a technical spec.
- Selects stack, tools, deployment target, and estimates build time.
- Surfaces blockers before Chiara starts building.
- Maps intent to skills; flags gaps in `intent_to_skill_map` for the learning loop.

### Chiara (Product-Generator)
Role: Implementation — step 3.
Responsibilities:
- Builds the deliverable: HTML, Python scripts, PDF, Streamlit app, markdown report.
- Follows Gianni's spec exactly. No scope creep.
- Uses cached skills from `global_settings.json` when available.
- Produces the file(s) that the user ultimately receives.

### Marco (Transaction-Manager)
Role: Finance — step 5.
Responsibilities:
- Looks up the product type in the pricing table.
- **Blocks delivery if `unknown_product: null`** — escalates to Luigi, never guesses.
- Generates invoice and receipt ID.
- Actuarial background: applies expected-value pricing; maintains a loss-development triangle; flags `actual_price / fair_price < 0.85` as P1.

### Francesca (Delivery-Agent)
Role: Final delivery — step 6.
Responsibilities:
- Executes the actual delivery: pushes code to GitHub, sends email, prints dispenser receipt, deploys to Vercel/Streamlit Cloud.
- Writes the audit log to `process/audit/YYYY-MM-DD_NNN_slug.md`.
- Discards session tokens after delivery — never stores OAuth credentials.
- **Triggers Valentina** after successful delivery to announce on active platforms.
- Triggers the learning loop post-delivery.

---

## Valentina (Profile Setup & Publishing Agent)

Role: Digital presence — runs in parallel with the delivery pipeline, not inline.
See full profile: [`valentina.md`](valentina.md)

Responsibilities:
- Generates platform-optimised bios for 9 platforms (character-limit accurate)
- Generates first posts for 9 platform formats in Luigi's voice
- Auto-publishes to Twitter/X (Tweepy), Telegram (Bot API), Discord (webhook), Reddit (PRAW)
- Manual handoff content for LinkedIn, Instagram, Product Hunt, GitHub README
- Maintains `process/profile_setup_checklist.md` — signup URLs + live status tracker
- **Confirmation gate before every publish** — Luigi approves all posts before they go out

Triggered by:
- Francesca signalling a new deliverable is ready to announce
- New platform account creation (fill profile + post first content)
- Weekly publishing schedule

```bash
cd deliverables/2026-05-23_010_profile-setup
python main.py --list              # see all platforms + publish method
python main.py --generate          # generate all bios + first posts → output/
python main.py --publish telegram  # confirm + send
```

---

## Risk Agents

Five agents operating as an autonomous risk management layer. Invoked on every new build, deployment, or significant operational change. Luigi retains final decision authority.

See full architecture: [`risk/README.md`](risk/README.md) and [`framework/ai_risk_management_team.md`](../framework/ai_risk_management_team.md)

**Actuarial baseline:** Every risk agent quantifies findings as `P(event) × impact × blast_radius` → Risk Units (RU). Flags trigger at 2σ deviation from the rolling baseline.

| Agent | Focus | Profile |
|---|---|---|
| Technical Auditor | Code, security, deployments | `risk/technical_auditor.md` |
| Financial Controller | Costs, pricing, invoices | `risk/financial_controller.md` |
| Operational Monitor | Uptime, automations, pipelines | `risk/operational_monitor.md` |
| Reputation Guardian | Output quality, demos, client feedback | `risk/reputation_guardian.md` |
| Compliance Agent | Data privacy, API terms, documentation | `risk/compliance_agent.md` |

---

## Research Department

Four agents continuously scanning GitHub for emerging AI tools. See [`research/README.md`](research/README.md).

| Agent | Role |
|---|---|
| Scout | Searches GitHub API across 15 AI topics |
| Analyst | Scores repos: stars(30%) + activity(25%) + growth(25%) + community(20%) |
| Curator | Deduplicates, categorises into 5 taxonomy groups |
| Reporter | Generates markdown digest + Streamlit dashboard |

```bash
python scripts/github_research/main.py --topics llm rag ai-agents
streamlit run deliverables/github-research/streamlit_research_app.py
```

Scheduled: daily S-tier alert (07:00 UTC) + weekly digest (Monday 08:00 UTC) via GitHub Actions.

---

*Risk agents invoked via `process/risk_review_process.md`. All findings route to Luigi for final disposition.*
