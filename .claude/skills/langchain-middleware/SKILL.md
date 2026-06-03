---
name: langchain-middleware
description: LangChain callbacks, tracing, and middleware patterns — LangSmith tracing, custom callbacks for Streamlit streaming, and token usage tracking. Load when adding observability or streaming UI to a LangChain/LangGraph pipeline.
---

# LangChain Middleware

## LangSmith Tracing

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls_..."   # from env var / Streamlit Secrets
os.environ["LANGCHAIN_PROJECT"] = "aistudio-accademia-milano"

# All subsequent chain/graph invocations are traced automatically
result = graph.invoke(initial_state, config=config)
```

## Streamlit Streaming Callback

```python
import streamlit as st
from langchain_core.callbacks import BaseCallbackHandler

class StreamlitStreamingHandler(BaseCallbackHandler):
    def __init__(self, container):
        self.container = container
        self.text = ""

    def on_llm_new_token(self, token: str, **kwargs):
        self.text += token
        self.container.markdown(self.text)

# Usage in Streamlit
output_container = st.empty()
handler = StreamlitStreamingHandler(output_container)

result = llm.invoke(messages, config={"callbacks": [handler]})
```

## Token Usage Tracking

```python
from langchain_core.callbacks import UsageMetadataCallbackHandler

usage_handler = UsageMetadataCallbackHandler()
result = chain.invoke(inputs, config={"callbacks": [usage_handler]})

print(usage_handler.usage_metadata)
# {"input_tokens": 250, "output_tokens": 180, "total_tokens": 430}
```

## Config Injection (RunnableConfig)

Pass config through the entire chain for provider switching and callbacks:

```python
config = {
    "configurable": {"provider": "anthropic"},
    "callbacks": [handler],
    "tags": ["production", "claim-processing"],
    "metadata": {"case_id": "CASE-ABC123"},
}

result = graph.invoke(initial_state, config=config)
```

## Rate Limiting / Retry

```python
from langchain_core.runnables import RunnableRetry

resilient_chain = RunnableRetry(
    bound=prompt | llm | JsonOutputParser(),
    retry_exception_types=(Exception,),
    max_attempt_number=3,
    wait_exponential_jitter=True,
)

result = resilient_chain.invoke(inputs)
```

## This Repo's Observability Convention

- LangSmith: optional (set `LANGCHAIN_API_KEY` in env if tracing is needed)
- Streamlit streaming: use `StreamlitStreamingHandler` for all interactive apps
- Token costs: log in audit log under `learning_flags` if spend is significant
- Error logging: every node catches exceptions and sets `state["error"]` — no silent failures
