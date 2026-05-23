"""
embed_index.py — Walk the repo, chunk every file, generate embeddings, save index.

Usage:
    python -m scripts.embed_index [--provider local|openai] [--model MODEL]

Providers:
    local   — sentence-transformers all-MiniLM-L6-v2  (no API key, runs offline)
    openai  — text-embedding-3-small                  (requires OPENAI_API_KEY)
"""

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent

INCLUDE_GLOBS = [
    "scripts/**/*.py",
    "templates/**/*.py",
    "agents/**/*.md",
    "config/**/*.json",
    "process/**/*.md",
    "process/**/*.yaml",
    "community/**/*.md",
    "deliverables/**/*.md",
    "deliverables/**/*.py",
    "tests/**/*.py",
]

EXCLUDE_PARTS = {"__pycache__", ".git", "data"}


def should_include(path: Path) -> bool:
    return not any(part in EXCLUDE_PARTS for part in path.parts)


def collect_files() -> list[Path]:
    files: list[Path] = []
    for glob in INCLUDE_GLOBS:
        for p in ROOT.glob(glob):
            if should_include(p) and p.is_file():
                files.append(p)
    return sorted(set(files))


def chunk_text(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    if not words:
        return [text] if text.strip() else []
    chunks: list[str] = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + size])
        if chunk.strip():
            chunks.append(chunk)
        i += size - overlap
    return chunks or [text[:2000]]


def build_chunks(files: list[Path]) -> list[dict]:
    chunks: list[dict] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = str(f.relative_to(ROOT))
        for i, chunk in enumerate(chunk_text(text)):
            chunks.append(
                {
                    "id": f"{rel}::{i}",
                    "source": rel,
                    "file_type": f.suffix.lstrip("."),
                    "chunk_index": i,
                    "text": chunk,
                }
            )
    return chunks


def embed_local(texts: list[str], model_name: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    return model.encode(texts, show_progress_bar=True, normalize_embeddings=True)


def embed_openai(texts: list[str], model_name: str) -> np.ndarray:
    from openai import OpenAI

    client = OpenAI()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), 100):
        resp = client.embeddings.create(model=model_name, input=texts[i : i + 100])
        vectors.extend(e.embedding for e in resp.data)
    return np.array(vectors, dtype=np.float32)


def save_index(chunks: list[dict], embeddings: np.ndarray, index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    with (index_dir / "chunks.jsonl").open("w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    np.save(str(index_dir / "embeddings.npy"), embeddings)
    # Metadata
    meta = {
        "total_chunks": len(chunks),
        "embedding_dim": int(embeddings.shape[1]) if embeddings.ndim == 2 else 0,
        "sources": sorted({c["source"] for c in chunks}),
    }
    (index_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[embed_index] Saved {len(chunks)} chunks → {index_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["local", "openai"], default="local")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    model = args.model or (
        "all-MiniLM-L6-v2" if args.provider == "local" else "text-embedding-3-small"
    )

    print("[embed_index] Collecting files...")
    files = collect_files()
    print(f"[embed_index] Found {len(files)} files")

    chunks = build_chunks(files)
    print(f"[embed_index] Built {len(chunks)} chunks")

    texts = [c["text"] for c in chunks]
    print(f"[embed_index] Embedding with {args.provider}:{model} ...")
    embeddings = embed_local(texts, model) if args.provider == "local" else embed_openai(texts, model)

    save_index(chunks, embeddings, ROOT / "data" / "index")


if __name__ == "__main__":
    main()
