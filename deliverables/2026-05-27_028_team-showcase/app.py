"""
AI Studio Accademia Milano — Team Showcase
Deliverable 025 · 2026-05-27
"""

import streamlit as st
import json
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Studio Accademia Milano — The Team",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Load brand & stats ────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]

@st.cache_data
def load_brand():
    p = REPO_ROOT / "config" / "brand.json"
    return json.loads(p.read_text()) if p.exists() else {}

@st.cache_data
def load_stats():
    p = REPO_ROOT / "config" / "global_settings.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    return d.get("agent_stats", {})

brand = load_brand()
stats = load_stats()

studio_name = brand.get("studio", {}).get("name", "AI Studio Accademia Milano")
tagline = brand.get("studio", {}).get("tagline", "One-human AI enterprise — tangible deliverables, every time.")


def agent_task_count(name: str) -> int:
    agent = stats.get(name, {})
    return sum(v.get("count", 0) for v in agent.get("task_stats", {}).values())


def agent_success_rate(name: str) -> float:
    agent = stats.get(name, {})
    tasks = agent.get("task_stats", {})
    if not tasks:
        return 1.0
    rates = [v.get("success_rate", 1.0) for v in tasks.values()]
    return sum(rates) / len(rates)


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Reset & base ── */
  .stApp { background: #0d0f14; }
  h1, h2, h3, h4, p, li, span { color: #e8eaf0; }

  /* ── Hero ── */
  .hero {
    background: linear-gradient(135deg, #1a1d2e 0%, #12151f 60%, #0d1a2e 100%);
    border: 1px solid #2a3050;
    border-radius: 16px;
    padding: 48px 40px 36px;
    text-align: center;
    margin-bottom: 8px;
  }
  .hero h1 { font-size: 2.6rem; font-weight: 800; margin: 0 0 8px;
    background: linear-gradient(90deg,#7eb8f7,#a78bfa,#f0abfc);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .hero .tagline { font-size: 1.1rem; color: #8892a8; margin: 0 0 20px; }
  .hero .meta { font-size: 0.85rem; color: #555e78; }

  /* ── Section label ── */
  .section-label {
    font-size: 0.75rem; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: #5a6a8a;
    margin: 40px 0 16px; border-bottom: 1px solid #1e2436; padding-bottom: 8px;
  }

  /* ── Pipeline row ── */
  .pipeline-row {
    display: flex; align-items: center; gap: 0;
    overflow-x: auto; margin-bottom: 24px;
  }
  .pipe-step {
    flex: 1; min-width: 120px;
    background: #151824; border: 1px solid #252c44;
    border-radius: 12px; padding: 18px 14px 14px;
    text-align: center; position: relative;
  }
  .pipe-step:hover { border-color: #4a6fa5; background: #1a1f30; }
  .pipe-arrow { color: #3a4a6a; font-size: 1.4rem; padding: 0 4px; flex-shrink: 0; }
  .pipe-num {
    display: inline-block; width: 24px; height: 24px; line-height: 24px;
    border-radius: 50%; background: #1e3a5f; color: #7eb8f7;
    font-size: 0.75rem; font-weight: 700; margin-bottom: 8px;
  }
  .pipe-name { font-size: 1rem; font-weight: 700; color: #d0d8f0; margin: 4px 0 2px; }
  .pipe-title { font-size: 0.7rem; color: #6a7a9a; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 6px; }
  .pipe-role { font-size: 0.78rem; color: #8892a8; line-height: 1.4; }

  /* ── Agent card ── */
  .agent-card {
    background: #151824; border: 1px solid #252c44;
    border-radius: 12px; padding: 22px 20px 18px;
    height: 100%; transition: border-color .2s;
  }
  .agent-card:hover { border-color: #4a6fa5; }
  .card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .card-icon { font-size: 1.8rem; }
  .card-name { font-size: 1.05rem; font-weight: 700; color: #d0d8f0; margin: 0; }
  .card-title { font-size: 0.7rem; color: #6a7a9a; letter-spacing: .08em;
    text-transform: uppercase; margin: 2px 0 0; }
  .card-body { font-size: 0.82rem; color: #8892a8; line-height: 1.55; }
  .card-body ul { padding-left: 16px; margin: 8px 0 0; }
  .card-body li { margin-bottom: 4px; }

  /* ── Badge ── */
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 20px;
    font-size: 0.68rem; font-weight: 600; letter-spacing: .04em; margin: 2px;
  }
  .badge-blue   { background: #1a3a5c; color: #7eb8f7; }
  .badge-purple { background: #2a1a4c; color: #a78bfa; }
  .badge-green  { background: #0f3020; color: #4ade80; }
  .badge-red    { background: #3a1010; color: #f87171; }
  .badge-amber  { background: #2a1a00; color: #fbbf24; }
  .badge-pink   { background: #3a0a2a; color: #f0abfc; }

  /* ── Stat pill ── */
  .stat-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: #1e2436; border-radius: 8px; padding: 6px 12px;
    font-size: 0.8rem; color: #8892a8; margin: 4px 4px 0 0;
  }
  .stat-val { font-weight: 700; color: #d0d8f0; font-size: 0.95rem; }

  /* ── Pipeline diagram ── */
  .pipeline-diagram {
    background: #0f1220; border: 1px solid #1e2a44;
    border-radius: 14px; padding: 24px 20px;
    margin-bottom: 8px;
  }

  /* ── Risk card ── */
  .risk-card {
    background: #12151e; border: 1px solid #2a1a1a;
    border-radius: 12px; padding: 18px 16px;
  }
  .risk-card:hover { border-color: #5a2020; }
  .risk-formula {
    font-family: monospace; font-size: 0.75rem;
    background: #1a1010; color: #f87171;
    border-radius: 6px; padding: 6px 10px;
    margin-top: 10px; display: block;
  }

  /* ── Team grid ── */
  .team-card {
    background: #151824; border: 1px solid #252c44;
    border-radius: 12px; padding: 18px 16px; margin-bottom: 12px;
  }
  .team-name { font-size: 0.9rem; font-weight: 700; color: #c0c8e8; margin: 0 0 4px; }
  .team-sub  { font-size: 0.72rem; color: #6a7a9a; margin: 0 0 8px; }
  .team-desc { font-size: 0.78rem; color: #7a8a9e; line-height: 1.5; }

  /* ── Footer ── */
  .footer {
    text-align: center; padding: 32px 0 16px;
    color: #3a4a6a; font-size: 0.78rem;
    border-top: 1px solid #1a2030; margin-top: 40px;
  }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HERO
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="hero">
  <h1>🎓 {studio_name}</h1>
  <p class="tagline">{tagline}</p>
  <p class="meta">Founded by Luigi Aceto · Milan, Italy · aistudiomilano.xyz</p>
</div>
""", unsafe_allow_html=True)


# ── Quick stats ───────────────────────────────────────────────────────────────
total_tasks = sum(agent_task_count(n) for n in ["Stacy", "Gianni", "Chiara", "Marco", "Francesca"])
cols = st.columns(5)
kpis = [
    ("24", "Deliverables shipped"),
    ("6", "Pipeline agents"),
    ("5", "Risk agents"),
    (str(total_tasks), "Tasks logged"),
    ("100%", "Success rate"),
]
for col, (val, label) in zip(cols, kpis):
    col.markdown(f"""
<div style="background:#151824;border:1px solid #252c44;border-radius:10px;
     padding:16px;text-align:center;">
  <div style="font-size:1.8rem;font-weight:800;color:#7eb8f7;">{val}</div>
  <div style="font-size:0.75rem;color:#6a7a9a;margin-top:4px;">{label}</div>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 6-AGENT PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<p class="section-label">The 6-Agent Delivery Pipeline</p>', unsafe_allow_html=True)

pipeline_agents = [
    {
        "num": "1",
        "name": "Stacy",
        "title": "Il Braccio Destro",
        "role": "Input Orchestrator",
        "desc": "Classifies intent, extracts entities, checks OAuth deps, routes to Gianni.",
        "icon": "🎯",
        "color": "#7eb8f7",
    },
    {
        "num": "2",
        "name": "Gianni",
        "title": "Il Tecnico",
        "role": "Request Analyzer",
        "desc": "Technical scoping — stack, tools, deploy target, time estimate, blockers.",
        "icon": "🔧",
        "color": "#a78bfa",
    },
    {
        "num": "3",
        "name": "Chiara",
        "title": "La Designer",
        "role": "Product Generator",
        "desc": "Builds the deliverable: HTML, Python, PDF, Streamlit. No scope creep.",
        "icon": "🎨",
        "color": "#f0abfc",
    },
    {
        "num": "4",
        "name": "Stacy QA",
        "title": "Quality Gate",
        "role": "Output Validator",
        "desc": "Validates format, security, disclaimer, completeness. Blocks if QA fails.",
        "icon": "✅",
        "color": "#4ade80",
    },
    {
        "num": "5",
        "name": "Marco",
        "title": "Il Banchiere",
        "role": "Transaction Manager",
        "desc": "Pricing lookup, invoice generation. Blocks on unknown_product: null.",
        "icon": "💰",
        "color": "#fbbf24",
    },
    {
        "num": "6",
        "name": "Francesca",
        "title": "La Venditrice",
        "role": "Delivery Agent",
        "desc": "GitHub push, email, Vercel/Streamlit deploy. Writes audit log. Triggers learning loop.",
        "icon": "🚀",
        "color": "#fb923c",
    },
]

cols = st.columns(13)  # 6 cards + 5 arrows
card_cols = [cols[0], cols[2], cols[4], cols[6], cols[8], cols[10]]
arrow_cols = [cols[1], cols[3], cols[5], cols[7], cols[9]]

for i, (col, agent) in enumerate(zip(card_cols, pipeline_agents)):
    tc = agent_task_count(agent["name"].split()[0])
    sr = agent_success_rate(agent["name"].split()[0])
    sr_pct = f"{sr*100:.0f}%"
    with col:
        st.markdown(f"""
<div class="agent-card" style="border-top: 3px solid {agent['color']};">
  <div style="text-align:center;margin-bottom:10px;">
    <div style="font-size:2rem;">{agent['icon']}</div>
    <div style="display:inline-block;width:22px;height:22px;line-height:22px;
         border-radius:50%;background:#1e3a5f;color:{agent['color']};
         font-size:0.7rem;font-weight:700;margin-top:4px;">
      {agent['num']}
    </div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:1rem;font-weight:700;color:#d0d8f0;">{agent['name']}</div>
    <div style="font-size:0.65rem;color:{agent['color']};letter-spacing:.07em;
         text-transform:uppercase;margin:2px 0 6px;">{agent['title']}</div>
    <div style="font-size:0.68rem;color:#6a7a9a;font-weight:600;margin-bottom:8px;">{agent['role']}</div>
    <div style="font-size:0.75rem;color:#7a8a9e;line-height:1.45;text-align:left;">{agent['desc']}</div>
  </div>
  {"" if tc == 0 else f'<div style="margin-top:10px;display:flex;gap:6px;justify-content:center;flex-wrap:wrap;"><span class="badge badge-blue">{tc} tasks</span><span class="badge badge-green">{sr_pct}</span></div>'}
</div>""", unsafe_allow_html=True)

for col in arrow_cols:
    col.markdown("""
<div style="text-align:center;padding-top:60px;font-size:1.3rem;color:#3a4a6a;">→</div>
""", unsafe_allow_html=True)


# ── Luigi (Founder) ───────────────────────────────────────────────────────────
st.markdown('<p class="section-label">Founder</p>', unsafe_allow_html=True)

st.markdown("""
<div class="agent-card" style="border-left: 4px solid #f59e0b; max-width: 600px;">
  <div class="card-header">
    <div class="card-icon">👑</div>
    <div>
      <p class="card-name">Luigi Aceto</p>
      <p class="card-title">Il Fondatore · Founder & Final Authority</p>
    </div>
  </div>
  <div class="card-body">
    Sets strategy, pricing, and product direction. Final approval on unknown product types
    and risk escalations. The only person who can override Marco's pricing block.
    <br><br>
    <span class="badge badge-amber">Strategy</span>
    <span class="badge badge-amber">Pricing</span>
    <span class="badge badge-amber">Final Approval</span>
    <span class="badge badge-amber">Risk Escalations</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RISK AGENTS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<p class="section-label">Risk Agents — Autonomous Actuarial Oversight</p>', unsafe_allow_html=True)

st.markdown("""
<div style="background:#0f1218;border:1px solid #2a1a1a;border-radius:10px;
     padding:12px 18px;margin-bottom:20px;font-size:0.82rem;color:#9a7a7a;">
  Every risk agent quantifies findings as
  <code style="background:#1a0f0f;color:#f87171;padding:2px 6px;border-radius:4px;">
    RU = P(event) × impact × blast_radius
  </code>
  — flags trigger at <strong style="color:#fbbf24;">2σ deviation</strong> from rolling baseline.
  Risk is never a label — it is always a number.
</div>
""", unsafe_allow_html=True)

risk_agents = [
    {
        "icon": "🔍",
        "name": "Technical Auditor",
        "formula": "P(incident) × impact_hours × blast_radius",
        "desc": "Code quality, security vulnerabilities, architectural consistency. Flags unvalidated inputs, hardcoded secrets, missing rollbacks.",
        "badges": ["Code Quality", "Security", "Deployment"],
    },
    {
        "icon": "📊",
        "name": "Financial Controller",
        "formula": "E[revenue] − E[cost] − E[risk_reserve]",
        "desc": "Project economics and cost discipline. Pricing adequacy ratio < 0.85 → P1 flag. Maintains loss-development triangle.",
        "badges": ["Profitability", "API Spend", "Concentration Risk"],
    },
    {
        "icon": "⚙️",
        "name": "Operational Monitor",
        "formula": "P(SLA breach) via MTBF/MTTR survival model",
        "desc": "System uptime and automation health. Tracks failed jobs, deployment bottlenecks, degraded pipeline throughput.",
        "badges": ["Uptime", "Automation", "Pipeline Health"],
    },
    {
        "icon": "🛡️",
        "name": "Reputation Guardian",
        "formula": "P(churn | quality) × LTV → revenue-at-risk",
        "desc": "Output quality and public perception. Audits deliverables before handoff. Flags broken demos, unresolved complaints.",
        "badges": ["Quality", "Client Perception", "LTV"],
    },
    {
        "icon": "⚖️",
        "name": "Compliance Agent",
        "formula": "E[regulatory_cost] per open compliance gap",
        "desc": "Legal, data, and API compliance. Verifies data handling, ToS adherence. Flags missing disclosures and API violations.",
        "badges": ["Legal", "Privacy", "API ToS"],
    },
]

r_cols = st.columns(5)
for col, a in zip(r_cols, risk_agents):
    badges_html = " ".join(f'<span class="badge badge-red">{b}</span>' for b in a["badges"])
    with col:
        st.markdown(f"""
<div class="risk-card">
  <div style="font-size:1.6rem;margin-bottom:8px;">{a['icon']}</div>
  <div style="font-size:0.9rem;font-weight:700;color:#e0a0a0;margin-bottom:6px;">{a['name']}</div>
  <div style="font-size:0.77rem;color:#8a7a7a;line-height:1.45;margin-bottom:8px;">{a['desc']}</div>
  <div>{badges_html}</div>
  <code class="risk-formula">{a['formula']}</code>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SPECIALIST AGENTS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<p class="section-label">Specialist Agents</p>', unsafe_allow_html=True)

spec_cols = st.columns(3)

with spec_cols[0]:
    st.markdown("""
<div class="agent-card" style="border-top: 3px solid #f0abfc;">
  <div class="card-header">
    <div class="card-icon">✨</div>
    <div>
      <p class="card-name">Valentina</p>
      <p class="card-title">Digital Identity & Content Agent</p>
    </div>
  </div>
  <div class="card-body">
    Owns digital identity, brand positioning, and content publishing — runs in
    <strong style="color:#f0abfc">parallel</strong> with the pipeline, not inline.
    <ul>
      <li>Platform-optimised bios for 8+ networks</li>
      <li>GitHub activity → LinkedIn/Twitter posts</li>
      <li>Weekly content generation &amp; publishing</li>
      <li>Editorial calendar &amp; stale account alerts</li>
    </ul>
    <span class="badge badge-pink">Brand Voice</span>
    <span class="badge badge-pink">Publishing</span>
    <span class="badge badge-pink">Content</span>
  </div>
</div>
""", unsafe_allow_html=True)

with spec_cols[1]:
    st.markdown("""
<div class="agent-card" style="border-top: 3px solid #f87171;">
  <div class="card-header">
    <div class="card-icon">🔒</div>
    <div>
      <p class="card-name">Lorenzo</p>
      <p class="card-title">Security & Prompt Injection Monitor</p>
    </div>
  </div>
  <div class="card-body">
    Passive security layer — always watching, never blocking legitimate work.
    <ul>
      <li>Prompt injection detection on every input</li>
      <li>Flags suspicious patterns to Luigi</li>
      <li>P1 issue creation 30 days before token/domain expiry</li>
      <li>Coordinates with IT Staff on credential hygiene</li>
    </ul>
    <span class="badge badge-red">Injection Detection</span>
    <span class="badge badge-red">Expiry Tracking</span>
  </div>
</div>
""", unsafe_allow_html=True)

with spec_cols[2]:
    st.markdown("""
<div class="agent-card" style="border-top: 3px solid #60a5fa;">
  <div class="card-header">
    <div class="card-icon">🖥️</div>
    <div>
      <p class="card-name">IT Staff</p>
      <p class="card-title">Infrastructure & Accounts Management</p>
    </div>
  </div>
  <div class="card-body">
    Advisory only — Luigi has final word on every action.
    <ul>
      <li>Maintains <code>accounts_registry.yaml</code></li>
      <li>DNS, domain, email, hosting configuration</li>
      <li>API token wiring &amp; credential management</li>
      <li>Structured confirmation before every write</li>
    </ul>
    <span class="badge badge-blue">DNS</span>
    <span class="badge badge-blue">Hosting</span>
    <span class="badge badge-blue">Credentials</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPARTMENT TEAMS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<p class="section-label">Department Teams</p>', unsafe_allow_html=True)

dept_cols = st.columns(4)

departments = [
    {
        "icon": "🧠",
        "name": "RAG Team",
        "color": "#a78bfa",
        "members": [
            ("Indexer", "scripts/rag/embed_repo.py"),
            ("Retriever", "scripts/rag/retrieve_repo.py"),
            ("Synthesizer", "scripts/rag/synthesize.py"),
            ("Context Injector", "Always-on UserPromptSubmit hook"),
        ],
        "desc": "Semantic memory over the entire repo using FAISS + BM25. Top-5 chunks injected before every response.",
    },
    {
        "icon": "🔭",
        "name": "Research Department",
        "color": "#34d399",
        "members": [
            ("Scout", "GitHub search across AI/ML topics"),
            ("Analyst", "Weighted actuarial scoring"),
            ("Curator", "Dedup + categorisation"),
            ("Reporter", "Weekly digest + Streamlit dashboard"),
        ],
        "desc": "Continuously scans GitHub for emerging AI tools. Scores on stars, activity, growth, community.",
    },
    {
        "icon": "🏗️",
        "name": "Input Gateway",
        "color": "#fb923c",
        "members": [
            ("Pablo", "PipelineAdapter + FastAPI /submit"),
            ("Sofia", "Streamlit form + live pipeline status"),
            ("Carlos", "Telegram bot + WhatsApp webhook"),
        ],
        "desc": "Three input channels that normalise user requests through a shared PipelineAdapter before touching Stacy.",
    },
    {
        "icon": "⚡",
        "name": "V2 Improvement Squad",
        "color": "#fbbf24",
        "members": [
            ("Quality Reliability Lead", "SLOs, observability, tests"),
            ("Core Architect", "Stack regrets, coupling, reusables"),
            ("API Product Designer", "Surface area, conversion paths"),
            ("Devil's Advocate", "Hidden costs, veto analysis"),
        ],
        "desc": "Second pass over delivered products when QA flags a defect or pricing adequacy < 0.85.",
    },
]

for col, dept in zip(dept_cols, departments):
    members_html = "".join(
        f'<div style="display:flex;gap:6px;align-items:flex-start;margin-bottom:6px;">'
        f'<span style="color:{dept["color"]};font-size:0.8rem;flex-shrink:0;">▸</span>'
        f'<div><div style="font-size:0.8rem;font-weight:600;color:#c0c8e8;">{m[0]}</div>'
        f'<div style="font-size:0.7rem;color:#6a7a9a;">{m[1]}</div></div></div>'
        for m in dept["members"]
    )
    with col:
        st.markdown(f"""
<div class="agent-card" style="border-top: 3px solid {dept['color']};">
  <div style="font-size:1.8rem;margin-bottom:6px;">{dept['icon']}</div>
  <div style="font-size:1rem;font-weight:700;color:#d0d8f0;margin-bottom:4px;">{dept['name']}</div>
  <div style="font-size:0.77rem;color:#7a8a9e;margin-bottom:14px;line-height:1.45;">{dept['desc']}</div>
  {members_html}
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# OPEN ISSUES TRACKER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<p class="section-label">Open Issues</p>', unsafe_allow_html=True)

issues = [
    ("ISS-002", "P1", "Build process/intent_registry.yaml"),
    ("ISS-003", "P2", "Unified credential manager"),
    ("ISS-004", "P2", "Build templates/ library (InvoiceTemplate, ChatbotTemplate)"),
    ("ISS-005", "P2", "Tiered thresholds in learning_loop.py"),
    ("ISS-006", "P2", "Source citation for advisory outputs"),
    ("ISS-009", "P3", "Schedule GitHub Research runs (cron + digest commit)"),
    ("ISS-010", "P2", "Add hosting_target required field for *_deploy_* intents"),
    ("ISS-011", "P1", "Acquire dispenser credentials before go-live"),
    ("ISS-012", "P2", "Implement LLMClassifier for free-text dispenser requests"),
    ("ISS-018", "P1", "Pablo: PipelineAdapter + FastAPI /submit + HMAC middleware"),
    ("ISS-019", "P1", "Sofia: Streamlit form wired to PipelineAdapter"),
    ("ISS-020", "P1", "Carlos: Telegram bot + WhatsApp webhook wired to PipelineAdapter"),
    ("ISS-021", "P2", "Deploy Input Gateway: all three channels live"),
    ("ISS-022", "P1", "Crash-recovery flush: periodic checkpoint write"),
]

priority_colors = {"P1": "#f87171", "P2": "#fbbf24", "P3": "#60a5fa"}

rows_per_col = (len(issues) + 1) // 2
left_issues = issues[:rows_per_col]
right_issues = issues[rows_per_col:]

iss_cols = st.columns(2)
for col, group in zip(iss_cols, [left_issues, right_issues]):
    with col:
        for issue_id, priority, title in group:
            pc = priority_colors.get(priority, "#8892a8")
            st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:8px 14px;
     background:#151824;border:1px solid #252c44;border-radius:8px;margin-bottom:6px;">
  <code style="font-size:0.72rem;color:#5a6a8a;flex-shrink:0;">{issue_id}</code>
  <span style="background:{pc}22;color:{pc};font-size:0.65rem;font-weight:700;
        padding:2px 6px;border-radius:4px;flex-shrink:0;">{priority}</span>
  <span style="font-size:0.8rem;color:#8892a8;">{title}</span>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="footer">
  {studio_name} · Deliverable 025 · 2026-05-27<br>
  luigi@aistudiomilano.xyz · aistudiomilano.xyz
</div>
""", unsafe_allow_html=True)
