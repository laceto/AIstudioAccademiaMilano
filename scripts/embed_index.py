"""
embed_index.py — Thin wrapper. Delegates to scripts.rag.embed_repo.

The RAG Indexer agent (scripts/rag/embed_repo.py) is now the canonical
implementation: kitai batch API, FAISS vectorstore, incremental registry.

Usage (unchanged — backward compatible):
    python -m scripts.embed_index [--provider local|openai]
"""

import argparse
import json
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

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
    "wiki/**/*.md",
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
            chunks.append({"id": f"{rel}::{i}", "source": rel, "file_type": f.suffix.lstrip("."), "chunk_index": i, "text": chunk})
    return chunks


def embed_local(texts: list[str], model_name: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    return model.encode(texts, show_progress_bar=True, normalize_embeddings=True)


def embed_openai(texts: list[str], model_name: str) -> np.ndarray:
    from openai import OpenAI
    from langchain_core.documents import Document
    from kitai.batch import (
        build_embedding_tasks, submit_batch_job,
        poll_until_complete, download_batch_results, parse_embedding_results,
    )
    client = OpenAI()
    docs = [Document(page_content=t, metadata={"id": i}) for i, t in enumerate(texts)]
    tasks = build_embedding_tasks(docs, model=model_name)
    job_id = submit_batch_job(client, tasks)
    print(f"[embed_index] Batch submitted: {job_id}")
    completed = poll_until_complete(client, [job_id], poll_interval=30.0)
    if job_id not in completed:
        raise RuntimeError(f"Batch {job_id} did not complete — check OpenAI dashboard")
    results = download_batch_results(client, job_id)
    pairs = parse_embedding_results(results)
    id_to_emb = {int(cid.removeprefix("custom_id_")): emb for cid, emb in pairs}
    vectors = [id_to_emb[i] for i in range(len(texts))]
    return np.array(vectors, dtype=np.float32)


def save_index(chunks: list[dict], embeddings: np.ndarray, index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    with (index_dir / "chunks.jsonl").open("w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    np.save(str(index_dir / "embeddings.npy"), embeddings)
    meta = {"total_chunks": len(chunks), "embedding_dim": int(embeddings.shape[1]) if embeddings.ndim == 2 else 0, "sources": sorted({c["source"] for c in chunks})}
    (index_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[embed_index] Saved {len(chunks)} chunks → {index_dir}")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["local", "openai"], default="local")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    model = args.model or ("all-MiniLM-L6-v2" if args.provider == "local" else "text-embedding-3-small")
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
