---
name: langchain-fundamentals
description: Canonical LangChain LCEL patterns for this repo — chains, prompts, output parsers, and RunnableConfig. Load before writing any LangChain chain or prompt template code.
---

# LangChain Fundamentals

## Canonical Chain Pattern (LCEL)

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableConfig

# JSON output (most common in agent nodes)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are X. Return ONLY valid JSON: {{\"key\": \"value\"}}"),
    ("human", "{input}"),
])
result: dict = (prompt | llm | JsonOutputParser()).invoke({"input": state["field"]})

# String output
text: str = (prompt | llm | StrOutputParser()).invoke({"input": state["field"]})
```

## Prompt Template Rules

- Always use double braces `{{}}` for literal curly braces in system prompts
- Single braces `{}` are template variables — must match `.invoke()` dict keys
- Keep system prompt focused: role + output format + one example
- Specify "Return ONLY valid JSON" when using JsonOutputParser — no markdown fences

## LLM Invocation via Factory

```python
from .llm_factory import get_llm

def my_node(state, config: RunnableConfig) -> dict:
    provider = (config or {}).get("configurable", {}).get("provider", "anthropic")
    llm = get_llm(provider, "fast")   # or "smart"
    result = (prompt | llm | JsonOutputParser()).invoke({...})
```

Never instantiate `ChatAnthropic` or `ChatOpenAI` directly in node functions — always use `get_llm`.

## Multi-turn Conversation

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Build message list from state
messages = [
    SystemMessage(content="You are a helpful assistant."),
    *state["messages"],
    HumanMessage(content=new_input),
]
response = llm.invoke(messages)
```

## Structured Output

```python
from pydantic import BaseModel

class AssessmentOutput(BaseModel):
    risk_level: str
    score: float
    notes: str

# Method 1: with_structured_output (preferred for complex schemas)
structured_llm = llm.with_structured_output(AssessmentOutput)
result: AssessmentOutput = structured_llm.invoke(messages)

# Method 2: JsonOutputParser (simpler, no Pydantic required)
result: dict = (prompt | llm | JsonOutputParser()).invoke(inputs)
```

## Error-resilient Parsing

```python
from langchain_core.output_parsers import JsonOutputParser
import json

try:
    result = (prompt | llm | JsonOutputParser()).invoke(inputs)
except Exception:
    # Fallback: try to extract JSON from raw string
    raw = llm.invoke(messages).content
    result = json.loads(raw.strip().strip("```json").strip("```"))
```

## Streaming

```python
for chunk in (prompt | llm).stream(inputs):
    print(chunk.content, end="", flush=True)
```
