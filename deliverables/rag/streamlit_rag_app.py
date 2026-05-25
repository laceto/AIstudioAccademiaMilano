"""
AI Studio Knowledge Search — RAG Chatbot
Ask questions about the entire codebase with natural language.
Deploy: streamlit run deliverables/rag/streamlit_rag_app.py
"""

import logging
import os
import sys
from pathlib import Path
from typing import Generator

import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from openai import OpenAI as _OpenAIClient

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import all business logic from retrieve_repo — single source of truth
from scripts.rag.retrieve_repo import (
    CHAT_MODEL,
    EMBED_DIMENSIONS,
    EMBEDDING_MODEL,
    FAISS_INDEX_NAME,
    K_BM25,
    K_SEMANTIC,
    VECTORSTORE_DIR,
    WEIGHTS_SPARSE,
    _OpenAIEmbeddings,
    extract_docs,
    load_vectorstore,
    retrieve_for_queries,
    translate_query,
)
from kitai.retriever import (
    create_BM25retriever_from_docs,
    create_hybrid_retriever,
    create_retriever,
    reorder_docs,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AI Studio Knowledge Search",
    page_icon=":mag:",
    layout="wide",
)

load_dotenv()

_api_key = os.environ.get("OPENAI_API_KEY", "")
if not _api_key:
    st.error(
        "OPENAI_API_KEY not found. Add it to your .env file and restart.",
        icon="🔑",
    )
    st.stop()


# ── Streaming answer generator ────────────────────────────────────────────────

def _stream_answer(
    query: str,
    context_docs: list[Document],
    client: _OpenAIClient,
) -> Generator[str, None, None]:
    """Stream LLM answer token-by-token using the same prompt as ask()."""
    context = "\n\n".join(doc.page_content for doc in context_docs)
    prompt = (
        "You are an expert on the AI Studio Accademia Milano repository.\n"
        "Use the following repo excerpts to answer the question precisely.\n"
        "If the context does not contain enough information, say so.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )
    stream = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ── UI helpers ────────────────────────────────────────────────────────────────

def _render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Source documents ({len(sources)})"):
        for i, src in enumerate(sources, 1):
            st.markdown(f"**[{i}]** `{src['path']}` — chunk {src['chunk']}")
            st.caption(src["snippet"])
            if i < len(sources):
                st.divider()


def _render_queries(queries: list[str]) -> None:
    if not queries or len(queries) <= 1:
        return
    with st.expander(f"Augmented queries ({len(queries)} total)"):
        for i, q in enumerate(queries):
            tag = " *(original)*" if i == 0 else ""
            st.markdown(f"**{i}.** {q}{tag}")


# ── Cached base resources — loaded once per Streamlit server process ──────────

@st.cache_resource(show_spinner="Loading vectorstore ...")
def _load_base_resources(
    folder: Path,
    index_name: str,
    embedding_model: str,
    embed_dimensions: int,
    api_key: str,
) -> tuple:
    """Load FAISS store, corpus docs, and shared API clients.

    api_key is an explicit parameter (not a closure) so that key rotation
    correctly invalidates the cache.
    """
    openai_client = _OpenAIClient(api_key=api_key)
    embeddings    = _OpenAIEmbeddings(model=embedding_model, client=openai_client)
    vs            = load_vectorstore(folder, index_name, embeddings)
    corpus        = extract_docs(vs)
    chat_model    = ChatOpenAI(model=CHAT_MODEL, temperature=0, api_key=api_key)
    logger.info("Corpus loaded: %d documents.", len(corpus))
    return vs, corpus, openai_client, chat_model


# ── Session state ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Sidebar — retrieval controls ──────────────────────────────────────────────

with st.sidebar:
    st.title("Retrieval settings")

    strategy = st.selectbox(
        "Query translation strategy",
        options=["expand", "decompose", "step_back", "none"],
        index=0,
        help=(
            "expand    — paraphrase variants (best for synonym/phrasing coverage)\n"
            "decompose — sub-questions (best for multi-part queries)\n"
            "step_back — abstract questions (best for foundational context)\n"
            "none      — single query, no translation"
        ),
    )

    k_semantic = st.slider(
        "Semantic k (FAISS)", min_value=1, max_value=20, value=K_SEMANTIC, step=1,
        help="Documents retrieved by the FAISS vector retriever per query.",
    )
    k_bm25 = st.slider(
        "BM25 k (keyword)", min_value=1, max_value=20, value=K_BM25, step=1,
        help="Documents retrieved by the BM25 keyword retriever per query.",
    )
    weights_sparse = st.slider(
        "BM25 weight (0 = pure semantic, 1 = pure keyword)",
        min_value=0.0, max_value=1.0, value=WEIGHTS_SPARSE, step=0.05,
        help="Blending weight for the EnsembleRetriever (RRF merge).",
    )

    st.divider()

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.caption(
        f"Vectorstore: `{VECTORSTORE_DIR.name}`\n\n"
        f"Embedding: `{EMBEDDING_MODEL}` ({EMBED_DIMENSIONS}-dim)\n\n"
        f"Chat: `{CHAT_MODEL}`"
    )

# ── Load base resources (cached) ──────────────────────────────────────────────

try:
    vs, corpus, openai_client, chat_model = _load_base_resources(
        VECTORSTORE_DIR, FAISS_INDEX_NAME, EMBEDDING_MODEL, EMBED_DIMENSIONS, _api_key
    )
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

# Rebuild hybrid retriever with live sidebar values (fast, < 0.5 s in-memory)
_bm25_ret   = create_BM25retriever_from_docs(docs=corpus, k=k_bm25)
_vector_ret = create_retriever(vs=vs, search_type="similarity", search_kwargs={"k": k_semantic})
hybrid = create_hybrid_retriever(
    sparse_retriever=_bm25_ret,
    semantic_retriever=_vector_ret,
    weights_sparse=weights_sparse,
)

# ── Main chat area ────────────────────────────────────────────────────────────

st.title("AI Studio Knowledge Search")
st.caption("Ask questions about the repo — code, agents, pricing, audit logs, wiki.")

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            _render_queries(msg.get("queries") or [])
            _render_sources(msg.get("sources") or [])

# ── Chat input handler ────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask about the repo..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        # Steps 1-3: translation + retrieval + reorder (no incremental output)
        with st.spinner("Retrieving context..."):
            queries = translate_query(chat_model, prompt, strategy=strategy)
            merged  = retrieve_for_queries(queries, hybrid)
            ordered = reorder_docs(merged)
            logger.info(
                "Context ready: %d docs from %d quer%s.",
                len(ordered), len(queries), "y" if len(queries) == 1 else "ies",
            )

        # Step 4: stream LLM answer token-by-token
        answer = st.write_stream(_stream_answer(prompt, ordered, openai_client))

        # Post-answer metadata expanders
        _render_queries(queries)

        sources = [
            {
                "path":    doc.metadata.get("path", ""),
                "chunk":   doc.metadata.get("chunk_index", 0),
                "snippet": doc.page_content[:200].replace("\n", " "),
                "guid":    doc.metadata.get("guid", ""),
            }
            for doc in ordered
        ]
        _render_sources(sources)

    st.session_state.messages.append({
        "role":    "assistant",
        "content": answer,
        "queries": queries,
        "sources": sources,
    })
