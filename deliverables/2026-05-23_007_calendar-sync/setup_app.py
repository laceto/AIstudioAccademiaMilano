"""
setup_app.py — Streamlit UI for configuring calendar credentials and testing the sync.

Deploy: streamlit run deliverables/2026-05-23_007_calendar-sync/setup_app.py

All credentials stored in Streamlit Secrets (never in code).
"""

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "deliverables" / "2026-05-23_007_calendar-sync"))

st.set_page_config(page_title="Calendar Sync Setup", page_icon="📅", layout="wide")
st.title("📅 WhatsApp → Calendar Sync")
st.caption("Send a message, get events created in Google, Outlook, and Apple Calendar.")

# —— Sidebar: credentials ————————————————————————————————————————

with st.sidebar:
    st.header("🔑 Credentials")
    st.caption("Stored in Streamlit Secrets — never in code.")

    openai_key = st.text_input("OpenAI API Key", type="password",
                               value=st.secrets.get("OPENAI_API_KEY", ""),
                               placeholder="sk-...")

    st.divider()
    st.subheader("🟢 Google Calendar")
    google_creds = st.text_area("credentials.json content", height=120,
                                placeholder="Paste OAuth2 client credentials JSON here")

    st.divider()
    st.subheader("🔵 Outlook / Microsoft")
    ms_client_id = st.text_input("MS_CLIENT_ID",
                                  value=st.secrets.get("MS_CLIENT_ID", ""))
    ms_tenant    = st.text_input("MS_TENANT_ID",
                                  value=st.secrets.get("MS_TENANT_ID", "common"))

    st.divider()
    st.subheader("⚪ Apple Calendar (iCloud)")
    apple_user = st.text_input("Apple ID email",
                                value=st.secrets.get("APPLE_ICLOUD_USERNAME", ""))
    apple_pass = st.text_input("App-specific password", type="password",
                                value=st.secrets.get("APPLE_APP_PASSWORD", ""),
                                help="Generate at appleid.apple.com → Security → App-specific passwords")

# —— Main: test a message ————————————————————————————————————————

st.subheader("💬 Test a Message")
sample = st.selectbox("Sample messages", [
    "Pranzo di lavoro con Marco domani alle 13 al Ristorante Borghese",
    "Board meeting next Friday 10:00-12:00 via Zoom https://zoom.us/j/123",
    "Call with London team Tuesday at 15:00 for 45 minutes",
    "Doctor appointment 28 May at 9:30am",
])
message = st.text_area("Message to parse", value=sample, height=80)

if st.button("🔍 Parse + Create Events", type="primary"):
    if not openai_key:
        st.error("❌ OpenAI API Key required for event parsing.")
        st.stop()

    os.environ["OPENAI_API_KEY"] = openai_key
    if google_creds:
        import json, tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(google_creds)
            os.environ["GOOGLE_CREDENTIALS_JSON"] = f.name
    if ms_client_id:
        os.environ["MS_CLIENT_ID"]  = ms_client_id
        os.environ["MS_TENANT_ID"]  = ms_tenant
    if apple_user:
        os.environ["APPLE_ICLOUD_USERNAME"] = apple_user
        os.environ["APPLE_APP_PASSWORD"]    = apple_pass

    from event_parser import extract_event
    from calendar_sync import sync_to_all_calendars

    with st.spinner("Parsing event with GPT-4o-mini..."):
        try:
            event = extract_event(message)
        except Exception as e:
            st.error(f"Parsing failed: {e}")
            st.stop()

    col1, col2 = st.columns(2)
    with col1:
        st.success("Parsed Event")
        st.json(event.model_dump())

    with st.spinner("Creating events in calendars..."):
        results = sync_to_all_calendars(event)

    with col2:
        st.subheader("Results")
        for r in results:
            if r.status == "ok":
                st.success(f"✅ {r.provider}" + (f" — [open]({r.link})" if r.link else ""))
            elif r.status == "skipped":
                st.info(f"⏭️ {r.provider}: not configured")
            else:
                st.error(f"❌ {r.provider}: {r.error}")

# —— Webhook instructions ————————————————————————————————————————

st.divider()
with st.expander("📖 How to connect WhatsApp / Telegram"):
    st.markdown("""
**Telegram (fastest, no approval needed)**
```bash
export TELEGRAM_BOT_TOKEN=your_token   # from @BotFather
python deliverables/2026-05-23_007_calendar-sync/bot_telegram.py
```

**WhatsApp via Twilio Sandbox (test in minutes)**
```bash
export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
python deliverables/2026-05-23_007_calendar-sync/bot_whatsapp.py
ngrok http 8080   # then set webhook URL in Twilio Console
```

**WhatsApp via Meta Cloud API (production)**  
Requires Meta Business verification. Set `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`,
`META_VERIFY_TOKEN`. Webhook endpoint: `/meta-whatsapp`.
    """)
