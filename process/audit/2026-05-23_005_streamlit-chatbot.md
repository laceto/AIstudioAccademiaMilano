# Audit Log — Request 005

```yaml
request_id: "005"
date: "2026-05-23"
time: "17:55"
input_type: text
raw_input: |
  A streamlit chatbot with calls to OpenAI
  with a user specific sys prompt
intent: chatbot_creation
product_type: chatbot_app

agents_invoked:
  - name: Stacy
    role: input_orchestrator
    duration_sec: 5
    status: success
    notes: >
      New intent 'chatbot_creation' — not in intent_to_skill_map.
      API key dependency detected (OpenAI). Stacy prompts user for OPENAI_API_KEY
      before routing. User provides key — stored in Streamlit secrets, not in code.
  - name: Gianni
    role: request_analyzer
    duration_sec: 4
    status: success
    notes: "Stack: Python + Streamlit + OpenAI SDK. Deploy: Streamlit Community Cloud. New MCP: streamlit_cloud."
  - name: Chiara
    role: product_generator
    duration_sec: 65
    status: success
    notes: "4 new skills exercised. Full working app generated. See deliverables/2026-05-23_005_chatbot/"
  - name: Stacy
    role: qa_agent
    duration_sec: 10
    status: success
    notes: "API key not hardcoded ✅. System prompt editable at runtime ✅. Streaming works ✅. History persists ✅."
  - name: Marco
    role: transaction_manager
    duration_sec: 15
    status: success
    notes: "chatbot_app not in pricing table. Marco blocked. Luigi approved €19.90."
  - name: Francesca
    role: delivery_agent
    duration_sec: 12
    status: success
    notes: "Deployed to Streamlit Community Cloud. Live URL generated."

skills_used:
  - streamlit_app_generation
  - openai_api_integration
  - chat_history_management
  - streamlit_secrets_handling
  - streamlit_cloud_deploy

mcp_tools_used:
  - streamlit_cloud_api
  - mcp__github__push_files

hooks_fired:
  - post_delivery_audit_log
  - api_key_dependency_check

qa_result: pass
qa_notes: "All checks passed. Note: user must have an active OpenAI account with credits."

payment:
  amount: "€19.90"
  method: card
  receipt_id: REC-20260523-005
  notes: "First chatbot app. Price set by Luigi: higher complexity than a static site."

delivery:
  method: url
  destination: https://user-chatbot-aistudio.streamlit.app
  confirmed: true

total_duration_sec: 111
outcome: success

learning_flags:
  new_skills:
    - streamlit_app_generation
    - openai_api_integration
    - chat_history_management
    - streamlit_secrets_handling
    - streamlit_cloud_deploy
  new_mcp:
    - streamlit_cloud_api
  new_hooks:
    - api_key_dependency_check
  pattern_match: "api_key_required (similar to oauth_dependency_check from req 002) — generalised hook created"
  risk_score: 2
  new_pricing:
    chatbot_app: "€19.90"
  new_intents:
    - chatbot_creation
```

---

## Pipeline Trace

### Step 1 — Stacy (Input-Orchestrator)

**⚠️ New intent:** `chatbot_creation` — not in map.  
**⚠️ New dependency detected:** OpenAI API key required. Same pattern as Gmail OAuth (req 002).

Stacy shows prompt at dispenser:
```
ℹ️ Questo chatbot chiama OpenAI. Ho bisogno della tua API key.

Inserisci la tua OPENAI_API_KEY:
[ sk-... _________________ ]

La chiave viene salvata solo in Streamlit Secrets — mai nel codice.
```

**Stacy output:**
```json
{
  "intent": "chatbot_creation",
  "product_type": "chatbot_app",
  "specs": {
    "framework": "streamlit",
    "ai_provider": "openai",
    "model": "gpt-4o",
    "feature_user_system_prompt": true,
    "streaming": true,
    "chat_history": true
  },
  "api_key_collected": true,
  "api_key_storage": "streamlit_secrets"
}
```

---

### Step 2 — Gianni (Request-Analyzer)

| Decision | Value |
|----------|-------|
| Language | Python 3.11+ |
| Framework | Streamlit 1.35+ |
| AI SDK | `openai` >= 1.0 |
| Deploy | Streamlit Community Cloud (free tier) |
| Files needed | `app.py`, `requirements.txt`, `.streamlit/secrets.toml` |
| Complexity | Medium — 3 components: UI + API calls + state |

```json
{
  "stack": "python-streamlit-openai",
  "deploy": "streamlit_community_cloud",
  "files": ["app.py", "requirements.txt", ".streamlit/secrets.toml"],
  "new_mcp_required": "streamlit_cloud_api"
}
```

---

### Step 3 — Chiara (Product-Generator)

See full code in `deliverables/2026-05-23_005_chatbot/`.

**What Chiara built:**
- `app.py` — full Streamlit chatbot (150 lines, streaming, history, editable system prompt)
- `requirements.txt` — pinned dependencies
- `.streamlit/secrets.toml` — API key template
- `README.md` — deploy instructions

---

### Step 4 — Stacy (QA)

| Check | Result |
|-------|--------|
| `OPENAI_API_KEY` read from `st.secrets`, never hardcoded | ✅ |
| System prompt editable by user at runtime (sidebar) | ✅ |
| Chat history persists across messages in session | ✅ |
| Streaming tokens displayed in real time | ✅ |
| Empty input blocked (no API call on blank submit) | ✅ |
| Model name configurable in sidebar | ✅ |
| Clear chat button works | ✅ |
| App runs on `streamlit run app.py` locally | ✅ |
| `requirements.txt` complete | ✅ |

**QA: PASS — production-ready.**

---

### Step 5 — Marco

`chatbot_app` not in pricing table. Marco blocks. Luigi: **€19.90**.
> Rationale: interactive app with live API calls + deploy = highest complexity delivered so far.

---

### Step 6 — Francesca

1. Pushed code to GitHub repo (user account)
2. Connected to Streamlit Community Cloud
3. Set `OPENAI_API_KEY` in Streamlit Secrets UI
4. App live at `https://user-chatbot-aistudio.streamlit.app`

---

### Final Output

```
✅ CHATBOT ONLINE

URL: https://user-chatbot-aistudio.streamlit.app
Framework: Streamlit
AI: OpenAI GPT-4o (streaming)
System prompt: configurabile dal menu laterale

Ricevuta: REC-20260523-005 · €19.90
```

---

### Process Summary

| Step | Agent | Time | Notes |
|------|-------|------|-------|
| 1. Input + API key | Stacy | 5s | New intent, API key collected |
| 2. Analysis | Gianni | 4s | 3 files planned |
| 3. Code generation | Chiara | 65s | 4 new skills |
| 4. QA | Stacy | 10s | 9/9 checks passed |
| 5. Payment | Marco | 15s | Block → Luigi → €19.90 |
| 6. Deploy | Francesca | 12s | Live on Streamlit Cloud |
| **Total** | | **111s** | ✅ |

---

## Learning Delta

| Change | Why |
|--------|-----|
| 5 new skills registered | First Streamlit + OpenAI request |
| `chatbot_creation` added to intent map | Manual resolution this time, auto next time |
| `streamlit_cloud_api` registered as MCP | First deploy to Streamlit Cloud |
| `api_key_dependency_check` hook promoted | Pattern mirrors `oauth_dependency_check` from req 002 — generalised to cover any external API key |
| `chatbot_app` → €19.90 in pricing table | Marco blocked correctly again — ISS-001 fix holding |
| ISS-003 insight: OpenAI key = same problem as OAuth | Both are external credentials. ISS-003 scope expanded: build a unified credential manager, not just OAuth caching |
