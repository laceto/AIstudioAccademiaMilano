"""
rag_chat.py — RAG chatbot over the AI Studio Accademia Milano knowledge base.

Retrieve relevant chunks from the index, then ask an LLM to synthesise
an answer grounded in those chunks.

Usage (from repo root):
    python -m scripts.rag_chat "How does invoice generation work?"
    python -m scripts.rag_chat "What skills does Chiara have?" --top-k 8
    python -m scripts.rag_chat "Explain the learning loop" --model gpt-4o

Requires:
    OPENAI_API_KEY env var (or Streamlit secrets when run inside an app)
    A pre-built index: python -m scripts.embed_index
"""

import argparse
import os

SYSTEM_PROMPT = (
    "You are the AI Studio Accademia Milano assistant. "
    "Answer questions using ONLY the provided context from the codebase and docs. "
    "Be concise and precise. "
    "If the answer is not in the context, say so explicitly — do not invent information."
)


def rag_answer(
    query: str,
    top_k: int = 5,
    chat_model: str = "gpt-4o-mini",
    embed_provider: str = "local",
) -> str:
    from scripts.retrieve import retrieve

    results = retrieve(query, top_k=top_k, provider=embed_provider)
    context = "\n\n---\n\n".join(
        f"[{r['source']}]\n{r['text']}" for r in results
    )
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            },
        ],
    )
    return resp.choices[0].message.content


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG chat over the AI Studio codebase")
    parser.add_argument("query", help="Your question")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--embed-provider", choices=["local", "openai"], default="local")
    args = parser.parse_args()

    answer = rag_answer(
        args.query,
        top_k=args.top_k,
        chat_model=args.model,
        embed_provider=args.embed_provider,
    )
    print(answer)


if __name__ == "__main__":
    main()
