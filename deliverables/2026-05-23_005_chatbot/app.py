"""Streamlit chatbot with OpenAI — user-configurable system prompt."""

import streamlit as st
from openai import OpenAI

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Chatbot",
    page_icon="🤖",
    layout="wide",
)

# ── Sidebar — configuration ────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")

    # API key: prefer Streamlit secrets, fall back to manual input
    api_key = st.secrets.get("OPENAI_API_KEY", None)
    if not api_key:
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-...",
            help="Your key is used only in this session and never stored.",
        )

    model = st.selectbox(
        "Model",
        ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
        index=0,
    )

    st.divider()

    system_prompt = st.text_area(
        "System prompt",
        value="You are a helpful, concise assistant. Answer in the same language the user writes in.",
        height=160,
        help="This instruction is sent to the model before every conversation.",
    )

    st.divider()

    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.caption("🔒 API key stored in Streamlit Secrets — never in code.")

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Chat header ────────────────────────────────────────────────────────────────
st.title("🤖 AI Chatbot")
st.caption(f"Model: `{model}` · System prompt active")

# ── Render history ─────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ─────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Message..."):

    if not api_key:
        st.error("❌ Enter your OpenAI API key in the sidebar to start.")
        st.stop()

    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build message list for API call
    messages_for_api = [
        {"role": "system", "content": system_prompt},
        *st.session_state.messages,
    ]

    # Stream the response
    client = OpenAI(api_key=api_key)
    with st.chat_message("assistant"):
        response_text = st.write_stream(
            chunk.choices[0].delta.content or ""
            for chunk in client.chat.completions.create(
                model=model,
                messages=messages_for_api,
                stream=True,
            )
            if chunk.choices[0].delta.content
        )

    st.session_state.messages.append({"role": "assistant", "content": response_text})
