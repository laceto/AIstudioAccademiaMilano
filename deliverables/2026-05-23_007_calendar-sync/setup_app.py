"""
setup_app.py — Streamlit config UI: test event parsing + calendar sync.
streamlit run deliverables/2026-05-23_007_calendar-sync/setup_app.py
"""

import os, sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
st.set_page_config(page_title="Calendar Sync Setup", page_icon="📅", layout="wide")
st.title("📅 WhatsApp → Calendar Sync")
st.caption("Send a message, get events in Google, Outlook, and Apple Calendar.")

with st.sidebar:
    st.header("🔑 Credentials")
    openai_key = st.text_input("OpenAI API Key", type="password", value=st.secrets.get("OPENAI_API_KEY", ""), placeholder="sk-...")
    st.divider()
    st.subheader("🟢 Google Calendar")
    google_creds = st.text_area("credentials.json content", height=100, placeholder="Paste OAuth2 JSON here")
    st.divider()
    st.subheader("🔵 Outlook")
    ms_client_id = st.text_input("MS_CLIENT_ID", value=st.secrets.get("MS_CLIENT_ID", ""))
    st.divider()
    st.subheader("⚪ Apple Calendar")
    apple_user = st.text_input("Apple ID email", value=st.secrets.get("APPLE_ICLOUD_USERNAME", ""))
    apple_pass = st.text_input("App-specific password", type="password", value=st.secrets.get("APPLE_APP_PASSWORD", ""),
                                help="Generate at appleid.apple.com → App-specific passwords")

message = st.text_area("Message to parse", value="Pranzo di lavoro con Marco domani alle 13 al Ristorante Borghese", height=80)

if st.button("🔍 Parse + Create Events", type="primary"):
    if not openai_key: st.error("❌ OpenAI API Key required."); st.stop()
    os.environ["OPENAI_API_KEY"] = openai_key
    if google_creds:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(google_creds); os.environ["GOOGLE_CREDENTIALS_JSON"] = f.name
    if ms_client_id: os.environ["MS_CLIENT_ID"] = ms_client_id
    if apple_user: os.environ["APPLE_ICLOUD_USERNAME"] = apple_user; os.environ["APPLE_APP_PASSWORD"] = apple_pass

    from event_parser import extract_event
    from calendar_sync import sync_to_all_calendars
    with st.spinner("Parsing..."):
        try: event = extract_event(message)
        except Exception as e: st.error(f"Parse failed: {e}"); st.stop()
    col1, col2 = st.columns(2)
    with col1:
        st.success("Parsed Event"); st.json(event.model_dump())
    with col2:
        st.subheader("Results")
        for r in sync_to_all_calendars(event):
            if r.status == "ok": st.success(f"✅ {r.provider}" + (f" — [open]({r.link})" if r.link else ""))
            elif r.status == "skipped": st.info(f"⏭️ {r.provider}: not configured")
            else: st.error(f"❌ {r.provider}: {r.error}")
