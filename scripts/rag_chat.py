"""
rag_chat.py — RAG chatbot over the AI Studio Accademia Milano knowledge base.

Usage (from repo root):
    python -m scripts.rag_chat "How does invoice generation work?"
    python -m scripts.rag_chat "What skills does Chiara have?" --top-k 8

Requires: OPENAI_API_KEY env var + a pre-built index (python -m scripts.embed_index)
"""

import argparse
import os

from config.brand import b, fmt

SYSTEM_PROMPT = (
    fmt(b("agent_personas.rag_chat_prompt")) + " "
    "Answer questions using ONLY the provided context from the codebase and docs. "
    "Be concise and precise. "
    "If the answer is not in the context, say so explicitly."
)


def rag_answer(query: str, top_k: int = 5, chat_model: str = "gpt-4o-mini", embed_provider: str = "local") -> str:
    from scripts.rag.retrieve_repo import retrieve
    docs = retrieve(query, top_k=top_k)
    context = "\n\n---\n\n".join(
        f"[{doc.metadata.get('path', '')}]\n{doc.page_content}" for doc in docs
    )
    from openai import OpenAI
    from kitai.batch import submit_batch_job, poll_until_complete, download_batch_results
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    task = {
        "custom_id": "rag-chat-0",
        "method":    "POST",
        "url":       "/v1/chat/completions",
        "body": {
            "model":    chat_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {query}"},
            ],
        },
    }
    job_id    = submit_batch_job(client, [task], endpoint="/v1/chat/completions")
    completed = poll_until_complete(client, [job_id], poll_interval=10.0)
    if job_id not in completed:
        raise RuntimeError(f"Batch {job_id} did not complete — check OpenAI dashboard")
    raw = download_batch_results(client, job_id)
    return raw[0]["response"]["body"]["choices"][0]["message"]["content"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--embed-provider", choices=["local", "openai"], default="local")
    args = parser.parse_args()
    print(rag_answer(args.query, top_k=args.top_k, chat_model=args.model, embed_provider=args.embed_provider))


if __name__ == "__main__":
    main()
