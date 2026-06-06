---
name: langchain-rag
description: Canonical RAG patterns for this repo — FAISS vectorstore, BM25 hybrid retrieval, retrieval chains, and the repo's own RAG infrastructure. Load before building any retrieval or RAG pipeline.
---

# LangChain RAG

## This Repo's RAG Infrastructure

```bash
# Build index (~30s)
python -m scripts.embed_index

# Query
python -m scripts.retrieve "how does Marco price unknown products?"

# Chat with repo knowledge
python -m scripts.rag_chat "explain the 6-agent pipeline"
```

Scripts: `scripts/rag/embed_repo.py`, `scripts/rag/retrieve_repo.py`, `scripts/rag/synthesize.py`

## Standard FAISS RAG Chain

```python
from langchain_community.vectorstores import FAISS
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Load existing index
vectorstore = FAISS.load_local("faiss_index", embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# RAG chain
prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer using only the provided context.\n\nContext:\n{context}"),
    ("human", "{question}"),
])

rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What is the pricing for a chatbot app?")
```

## Hybrid BM25 + FAISS (this repo's pattern)

```python
from scripts.rag.retrieve_repo import retrieve

# Returns top-k chunks using hybrid BM25+FAISS scoring
chunks = retrieve("what does Francesca do after delivery?", k=5)
for chunk in chunks:
    print(chunk["text"], chunk["score"])
```

## Building a Vectorstore

```python
from langchain_community.vectorstores import FAISS
from langchain_anthropic import ChatAnthropic
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(docs)

vectorstore = FAISS.from_documents(chunks, embeddings)
vectorstore.save_local("faiss_index")
```

## Retriever Options

```python
# Similarity search
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5})

# MMR (maximal marginal relevance — reduces redundancy)
retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5, "fetch_k": 20})

# Score threshold
retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.7},
)
```

## RAG in a LangGraph Node

```python
def rag_node(state: MyState, config: RunnableConfig) -> dict:
    from scripts.rag.retrieve_repo import retrieve
    chunks = retrieve(state["question"], k=5)
    context = "\n\n".join(c["text"] for c in chunks)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer using only the context below.\n\nContext:\n{context}"),
        ("human", "{question}"),
    ])
    llm = get_llm(_provider(config), "smart")
    answer = (prompt | llm | StrOutputParser()).invoke({
        "context": context,
        "question": state["question"],
    })
    return {"answer": answer, "messages": [AIMessage(content=f"[RAG] {answer[:100]}...")]}
```
