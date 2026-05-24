# /requirements — Show Requirements Manifest for a Product Type

**Usage:** `/requirements <product_type>`

**Examples:**
- `/requirements algo_trading`
- `/requirements email_automation`
- `/requirements linkedin_post_generator`
- `/requirements --list`

---

## What this command does

Prints the full Requirements Manifest for the given product type: all accounts, API keys, credentials, and signup URLs the user needs before implementation can start.

This is the same manifest Gianni presents at the start of every project intake. Use it manually when:
- A user asks "what do I need for X?"
- You're resuming a project and want to re-check credentials
- You're onboarding a new user to an existing deliverable

---

## How to run it

```bash
python scripts/requirements_checker.py <product_type>
```

Or from Python:
```python
from scripts.requirements_checker import format_requirements_manifest
print(format_requirements_manifest("algo_trading"))
```

---

## Available product types

Run `/requirements --list` to see all registered types with prices.

Current registry:

| Product type | Label | Price |
|---|---|---|
| `email_automation` | Email Automation (Gmail) | €14.90 |
| `calendar_assistant` | Calendar Assistant | €9.90 |
| `whatsapp_bot` | WhatsApp / Telegram Bot | €19.90 |
| `social_media_manager` | Social Media Manager | €14.90 |
| `algo_trading` | Algo Trading Bot (Alpaca) | €24.90 |
| `linkedin_post_generator` | LinkedIn Post Generator | €4.90 |
| `profile_setup` | Profile Setup & Publishing | €14.90 |
| `ai_assistant` | AI Assistant / Chatbot | €14.90 |
| `data_dashboard` | Data Dashboard / Analytics | €9.90 |

---

## Adding a new product type

Edit `config/requirements_registry.yaml` and add a new entry under `products:` and `pricing:`. The format is:

```yaml
my_new_product:
  label: "Human-readable name"
  required:
    - id: some_api_key
      name: "SOME_API_KEY"
      type: api_key
      signup_url: "https://..."
      notes: "Where to find it"
  optional:
    - id: optional_thing
      name: "Optional thing"
      type: account
      notes: "What it enables"
  manual_only:
    - id: manual_thing
      name: "Platform name"
      notes: "Why it's manual"
```

---

## Security reminder

After showing the manifest, always remind the user:
- Store API keys in environment variables, not in code
- Use `.env` + `python-dotenv` for local dev
- Use `st.secrets` for Streamlit apps
- Never commit `credentials.json`, `token.json`, or `.env` to git
