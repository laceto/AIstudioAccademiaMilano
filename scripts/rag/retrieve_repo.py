"""
retrieve_repo.py — Retriever Agent
Hybrid BM25 + FAISS retrieval over the repo vectorstore.
Mirrors rss_feed/pipeline/hybrid_rag.py exactly.

Public API:
    load_vectorstore(folder, index_name, embeddings_model) -> FAISS
        Load and validate FAISS store from disk. Raises FileNotFoundError if
        .faiss or .pkl files are missing.

    extract_docs(vs) -> list[Document]
        Pull all documents from the FAISS in-memory docstore.

    translate_query(chat_model, query, strategy) -> list[str]
        Expand a single query into an augmented pool via kitai.query_translation.
        Returns [original, ...augmented]; [0] is always the original.

    retrieve_for_queries(queries, hybrid) -> list[Document]
        Run each query through the hybrid retriever; deduplicate by guid.

    retrieve(query, *, top_k=12, strategy="none") -> list[Document]
        Real-time, no LLM call. Used by inject_context.py.

    ask(query, *, strategy="expand") -> dict
        {answer, sources, queries} — retrieval + GPT-4o-mini synthesis.

Resources are lazily loaded and cached at module level.
First call pays the FAISS + BM25 init cost (~5–30 s).
All subsequent calls within the same process are instant.

Usage:
    python -m scripts.rag.retrieve_repo "how does invoice pricing work?" --no-llm
    python -m scripts.rag.retrieve_repo "what agents handle email delivery?"
    python -m scripts.rag.retrieve_repo "explain the 6-agent pipeline" --strategy decompose
"""

import argparse
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from openai import OpenAI as _OpenAIClient

from config.brand import b, fmt
from kitai.batch import download_batch_results, poll_until_complete, submit_batch_job
from kitai.query_translation import decompose_query, expand_query, step_back_query
from kitai.retriever import (
    create_BM25retriever_from_docs,
    create_hybrid_retriever,
    create_retriever,
    reorder_docs,
)

ROOT             = Path(__file__).parent.parent.parent
VECTORSTORE_DIR  = ROOT / "data" / "vectorstore" / "repo"
FAISS_INDEX_NAME = "index"

EMBEDDING_MODEL  = "text-embedding-3-small"
EMBED_DIMENSIONS = 1536
CHAT_MODEL       = "gpt-4o-mini"
K_SEMANTIC       = 6
K_BM25           = 6
WEIGHTS_SPARSE   = 0.5
QUERY_STRATEGY   = "expand"

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


# ── Embeddings shim (avoids langchain_openai version conflicts) ───────────────

class _OpenAIEmbeddings(Embeddings):
    """Thin wrapper around the OpenAI client satisfying langchain_core.Embeddings.

    Intentionally uses synchronous OpenAI calls — FAISS similarity search and
    query embedding require immediate results and cannot use the async batch API.
    """

    def __init__(self, model: str, client: _OpenAIClient) -> None:
        self._model  = model
        self._client = client

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(
            input=texts, model=self._model, dimensions=EMBED_DIMENSIONS,
        )
        return [item.embedding for item in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# ── Vectorstore helpers ───────────────────────────────────────────────────────

def load_vectorstore(
    folder: Path,
    index_name: str,
    embeddings_model: _OpenAIEmbeddings,
) -> FAISS:
    """Load a FAISS index from disk, with pre-flight file checks.

    Raises:
        FileNotFoundError: If .faiss or .pkl files are missing.
            Message includes the remediation command.
    """
    faiss_file = folder / f"{index_name}.faiss"
    pkl_file   = folder / f"{index_name}.pkl"
    for f in (faiss_file, pkl_file):
        if not f.exists():
            raise FileNotFoundError(
                f"Expected vectorstore file not found: {f}\n"
                "Run: python -m scripts.rag.embed_repo"
            )
    log.info("Loading FAISS index from %s ...", folder)
    vs = FAISS.load_local(
        folder_path=str(folder),
        embeddings=embeddings_model,
        index_name=index_name,
        allow_dangerous_deserialization=True,  # safe: we own this .pkl
    )
    log.info("Loaded %d vectors.", vs.index.ntotal)
    return vs


def extract_docs(vs: FAISS) -> list[Document]:
    """Pull all Documents from the FAISS in-memory docstore.

    Used to build the BM25 index over the same corpus so both retrievers
    always see identical documents.
    """
    return list(vs.docstore._dict.values())


# ── Lazy resource cache ───────────────────────────────────────────────────────

_lazy: dict | None = None


def _get_resources() -> dict:
    """Load FAISS + BM25 corpus + clients once; cache for process lifetime."""
    global _lazy
    if _lazy is not None:
        return _lazy

    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not set. Add to .env or environment."
        )

    log.info("Loading RAG resources (first call) ...")
    openai_client    = _OpenAIClient(api_key=api_key)
    embeddings_model = _OpenAIEmbeddings(model=EMBEDDING_MODEL, client=openai_client)
    vs               = load_vectorstore(VECTORSTORE_DIR, FAISS_INDEX_NAME, embeddings_model)
    corpus           = extract_docs(vs)
    chat_model       = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    log.info("RAG ready: %d vectors, %d corpus docs.", vs.index.ntotal, len(corpus))
    _lazy = {
        "openai_client": openai_client,
        "chat_model":    chat_model,
        "vs":            vs,
        "corpus":        corpus,
    }
    return _lazy


# ── Hybrid retriever builder ──────────────────────────────────────────────────

def _build_hybrid(
    res: dict,
    k_semantic: int = K_SEMANTIC,
    k_bm25: int = K_BM25,
    weights: float = WEIGHTS_SPARSE,
):
    bm25   = create_BM25retriever_from_docs(docs=res["corpus"], k=k_bm25)
    vector = create_retriever(
        res["vs"], search_type="similarity", search_kwargs={"k": k_semantic},
    )
    return create_hybrid_retriever(
        sparse_retriever=bm25,
        semantic_retriever=vector,
        weights_sparse=weights,
    )


# ── Query translation ─────────────────────────────────────────────────────────

def translate_query(chat_model, query: str, strategy: str) -> list[str]:
    """Expand a single query into an augmented pool via kitai.query_translation.

    Args:
        chat_model: LangChain ChatOpenAI instance used by the translation chain.
        query:      Raw user question.
        strategy:   One of "expand", "decompose", "step_back", "none".

    Returns:
        Deduplicated list of query strings; [0] is always the original.

    Raises:
        ValueError: If strategy is not a recognised value.
    """
    if strategy == "none":
        return [query]

    if strategy == "expand":
        raw       = expand_query(chat_model, [query])
        augmented = [pq.paraphrased_query for pq in raw[0]]
    elif strategy == "decompose":
        raw       = decompose_query(chat_model, [query])
        augmented = [dq.decomposed_query for dq in raw[0]]
    elif strategy == "step_back":
        raw       = step_back_query(chat_model, [query], num_queries=2)
        augmented = [gq.general_query for gq in raw[0]]
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}. Choose: expand, decompose, step_back, none.")

    seen    = {query}
    queries = [query]
    for q in augmented:
        if q not in seen:
            queries.append(q)
            seen.add(q)

    log.info("Query translation [%s]: %d queries from %r", strategy, len(queries), query)
    for i, q in enumerate(queries):
        log.debug("  query %d: %s%s", i, q, " [original]" if i == 0 else "")
    return queries


# ── Retrieval + deduplication ─────────────────────────────────────────────────

def retrieve_for_queries(queries: list[str], hybrid) -> list[Document]:
    """Run each query through the hybrid retriever; deduplicate by guid.

    First-retrieved occurrence wins, preserving ranking signal from the
    original (first) query.
    """
    results: list[list[Document]] = hybrid.batch(queries)
    seen:    set[str]             = set()
    merged:  list[Document]       = []

    for q, docs in zip(queries, results):
        added = 0
        for doc in docs:
            guid = doc.metadata.get("guid", "")
            if guid not in seen:
                seen.add(guid)
                merged.append(doc)
                added += 1
        log.debug("Query %r -> %d retrieved, %d new after dedup.", q, len(docs), added)

    log.info(
        "Retrieved %d unique docs from %d quer%s.",
        len(merged), len(queries), "y" if len(queries) == 1 else "ies",
    )
    return merged


# ── Public API ────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    *,
    top_k: int = K_SEMANTIC + K_BM25,
    strategy: str = "none",
) -> list[Document]:
    """Real-time hybrid retrieval — no LLM call. Used by inject_context.py.

    Args:
        query:    Natural-language question.
        top_k:    Maximum docs to return after LongContextReorder.
        strategy: "none" for speed (no LLM translation); "expand" for coverage.

    Returns:
        Reordered list of Document objects, capped at top_k.
    """
    res    = _get_resources()
    hybrid = _build_hybrid(res)

    queries = translate_query(res["chat_model"], query, strategy)
    merged  = retrieve_for_queries(queries, hybrid)
    ordered = reorder_docs(merged)
    return ordered[:top_k]


def ask(
    query: str,
    *,
    strategy: str = QUERY_STRATEGY,
    k_semantic: int = K_SEMANTIC,
    k_bm25: int = K_BM25,
    weights_sparse: float = WEIGHTS_SPARSE,
) -> dict:
    """Full RAG pipeline: retrieve + LLM answer.

    Args:
        query:          Natural-language question.
        strategy:       Query translation strategy (expand/decompose/step_back/none).
        k_semantic:     FAISS docs retrieved per query.
        k_bm25:         BM25 docs retrieved per query.
        weights_sparse: BM25 blend weight (0.0 = pure semantic, 1.0 = pure keyword).

    Returns:
        dict with keys:
            "answer"  : str        — GPT-4o-mini generated answer.
            "sources" : list[dict] — retrieved docs with path, chunk, snippet, guid.
            "queries" : list[str]  — augmented query pool; [0] is original.
    """
    res    = _get_resources()
    hybrid = _build_hybrid(res, k_semantic=k_semantic, k_bm25=k_bm25, weights=weights_sparse)

    queries = translate_query(res["chat_model"], query, strategy)
    merged  = retrieve_for_queries(queries, hybrid)
    ordered = reorder_docs(merged)

    context  = "\n\n".join(doc.page_content for doc in ordered)
    prompt   = (
        fmt(b("agent_personas.rag_expert_prompt")) + "\n"
        "Use the following repo excerpts to answer the question precisely.\n"
        "If the context does not contain enough information, say so.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )
    task = {
        "custom_id": "ask-0",
        "method":    "POST",
        "url":       "/v1/chat/completions",
        "body": {
            "model":       CHAT_MODEL,
            "temperature": 0,
            "messages":    [{"role": "user", "content": prompt}],
        },
    }
    client    = res["openai_client"]
    job_id    = submit_batch_job(client, [task], endpoint="/v1/chat/completions")
    completed = poll_until_complete(client, [job_id], poll_interval=10.0)
    if job_id not in completed:
        raise RuntimeError(f"Batch {job_id} did not complete — check OpenAI dashboard")
    raw    = download_batch_results(client, job_id)
    answer = raw[0]["response"]["body"]["choices"][0]["message"]["content"]

    sources = [
        {
            "path":    doc.metadata.get("path", ""),
            "chunk":   doc.metadata.get("chunk_index", 0),
            "snippet": doc.page_content[:200].replace("\n", " "),
            "guid":    doc.metadata.get("guid", ""),
        }
        for doc in ordered
    ]
    log.info("ask() → %d sources, %d queries, strategy=%r.", len(sources), len(queries), strategy)
    return {"answer": answer, "sources": sources, "queries": queries}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Query the repo RAG index")
    parser.add_argument("query",      nargs="?",  help="Question to answer")
    parser.add_argument("--top-k",    type=int,   default=5)
    parser.add_argument("--strategy", choices=["expand", "decompose", "step_back", "none"], default=QUERY_STRATEGY)
    parser.add_argument("--json",     action="store_true", help="Output as JSON")
    parser.add_argument("--no-llm",   action="store_true", help="Retrieve only, no LLM synthesis")
    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        return

    if args.no_llm:
        docs = retrieve(args.query, top_k=args.top_k, strategy=args.strategy)
        if args.json:
            out = [{"path": d.metadata.get("path"), "chunk": d.metadata.get("chunk_index"), "snippet": d.page_content[:300]} for d in docs]
            print(json.dumps(out, indent=2))
        else:
            print(f"\n[retrieve] {len(docs)} results for: '{args.query}'")
            for i, doc in enumerate(docs, 1):
                print(f"\n{'='*60}")
                print(f"[{i}] {doc.metadata.get('path')} (chunk {doc.metadata.get('chunk_index')})")
                print("="*60)
                print(doc.page_content[:500])
    else:
        result = ask(args.query, strategy=args.strategy)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\nQUERY    : {args.query}")
            print(f"STRATEGY : {args.strategy} ({len(result['queries'])} queries)")
            if len(result["queries"]) > 1:
                print("\nAUGMENTED QUERIES:")
                for i, q in enumerate(result["queries"]):
                    tag = " [original]" if i == 0 else ""
                    print(f"  {i}. {q}{tag}")
            print(f"\nSOURCES ({len(result['sources'])}):")
            for i, src in enumerate(result["sources"], 1):
                print(f"  [{i}] {src['path']} (chunk {src['chunk']})")
                print(f"       {src['snippet'][:120]}...")
            print(f"\nANSWER:\n{result['answer']}")


if __name__ == "__main__":
    main()
