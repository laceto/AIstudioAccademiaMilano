from config.brand import b

_PROVIDERS = {
    "openai": {
        "import": "from openai import OpenAI",
        "key_name": "OPENAI_API_KEY",
        "client_cls": "OpenAI",
        "models": "[\"gpt-4o\", \"gpt-4o-mini\", \"gpt-3.5-turbo\"]",
        "stream": "(chunk.choices[0].delta.content or \"\" for chunk in client.chat.completions.create(model=model, messages=msgs, stream=True))",
    },
    "anthropic": {
        "import": "from anthropic import Anthropic",
        "key_name": "ANTHROPIC_API_KEY",
        "client_cls": "Anthropic",
        "models": "[\"claude-sonnet-4-6\", \"claude-haiku-4-5-20251001\"]",
        "stream": "client.messages.stream(model=model, max_tokens=2048, messages=msgs).__enter__().text_stream",
    },
    "groq": {
        "import": "from groq import Groq",
        "key_name": "GROQ_API_KEY",
        "client_cls": "Groq",
        "models": "[\"llama-3.3-70b-versatile\", \"mixtral-8x7b-32768\"]",
        "stream": "(chunk.choices[0].delta.content or \"\" for chunk in client.chat.completions.create(model=model, messages=msgs, stream=True))",
    },
}


class ChatbotTemplate:
    def __init__(self, provider: str, model: str):
        if provider not in _PROVIDERS:
            supported = ", ".join(sorted(_PROVIDERS))
            raise ValueError(
                f"Unsupported provider '{provider}'. Supported: {supported}"
            )
        self.provider = provider
        self.model = model
        self._cfg = _PROVIDERS[provider]

    def is_valid(self) -> bool:
        return self.provider in _PROVIDERS and bool(self.model)

    def render(self) -> str:
        c = self._cfg
        lines = [
            "import streamlit as st",
            c["import"],
            "",
            f'st.set_page_config(page_title="{b("ui_strings.chatbot_template_title")}", layout="wide")',
            f'st.title("{b("ui_strings.chatbot_template_title")}")',
            "",
            "with st.sidebar:",
            '    st.header("Settings")',
            "    system_prompt = st.text_area(",
            '        "System prompt",',
            '        value="You are a helpful AI assistant.",',
            "        height=120,",
            "    )",
            f"    model = st.selectbox(\"Model\", {c['models']})",
            '    if st.button("Clear conversation"):',
            "        st.session_state.messages = []",
            "",
            'if "messages" not in st.session_state:',
            "    st.session_state.messages = []",
            "",
            "for msg in st.session_state.messages:",
            '    with st.chat_message(msg["role"]):',
            '        st.markdown(msg["content"])',
            "",
            'if prompt := st.chat_input("Type your message..."):',
            '    st.session_state.messages.append({"role": "user", "content": prompt})',
            '    with st.chat_message("user"):',
            "        st.markdown(prompt)",
            "",
            f"    client = {c['client_cls']}(api_key=st.secrets[\"{c['key_name']}\"]) ",
            '    msgs = [{"role": "system", "content": system_prompt}] + st.session_state.messages',
            "",
            '    with st.chat_message("assistant"):',
            f"        response = st.write_stream({c['stream']})",
            "",
            '    st.session_state.messages.append({"role": "assistant", "content": response})',
        ]
        return "\n".join(lines)
