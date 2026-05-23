"""
retrieve.py — Query the embedded index and return top-K relevant chunks.

Usage (from repo root):
    python -m scripts.retrieve "how does invoice generation work?"
    python -m scripts.retrieve "what agents are available?" --top-k 10 --json
"""

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
INDEX_DIR = ROOT / "data" / "index"


def load_index() -> tuple[list[dict], np.ndarray]:
    chunks_path = INDEX_DIR / "chunks.jsonl"
    embeddings_path = INDEX_DIR / "embeddings.npy"
    if not chunks_path.exists() or not embeddings_path.exists():
        raise FileNotFoundError(
            f"Index not found at {INDEX_DIR}. Run: python -m scripts.embed_index"
        )
    chunks = [
        json.loads(line)
        for line in chunks_path.read_text().splitlines()
        if line.strip()
    ]
    embeddings = np.load(str(embeddings_path))
    return chunks, embeddings


def embed_query(
    query: str, provider: str = "local", model: str | None = None
) -> np.ndarray:
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI()
        resp = client.embeddings.create(
            model=model or "text-embedding-3-small", input=[query]
        )
        vec = np.array(resp.data[0].embedding, dtype=np.float32)
    else:
        from sentence_transformers import SentenceTransformer

        m = SentenceTransformer(model or "all-MiniLM-L6-v2")
        vec = m.encode([query], normalize_embeddings=True)[0]
    return vec


def cosine_similarity(query_vec: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(corpus, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    normalized = corpus / norms
    q_norm = np.linalg.norm(query_vec)
    q = query_vec / (q_norm if q_norm > 0 else 1e-9)
    return normalized @ q


def retrieve(
    query: str,
    top_k: int = 5,
    provider: str = "local",
    model: str | None = None,
) -> list[dict]:
    chunks, embeddings = load_index()
    query_vec = embed_query(query, provider=provider, model=model)
    scores = cosine_similarity(query_vec, embeddings)
    top_indices = np.argsort(scores)[::-1][:top_k]
    results = []
    for idx in top_indices:
        result = dict(chunks[int(idx)])
        result["score"] = float(scores[idx])
        results.append(result)
    return results


def format_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"\n{'=' * 60}")
        lines.append(f"Result {i} | score={r['score']:.3f} | {r['source']}")
        lines.append("=" * 60)
        lines.append(r["text"][:600])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the AI Studio knowledge index")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--provider", choices=["local", "openai"], default="local")
    parser.add_argument("--model", default=None)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        return

    results = retrieve(args.query, top_k=args.top_k, provider=args.provider, model=args.model)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(format_results(results))
        print(f"\n[retrieve] {len(results)} results for: '{args.query}'")


if __name__ == "__main__":
    main()
