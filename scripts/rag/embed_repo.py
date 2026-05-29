"""
embed_repo.py — Indexer Agent
Walks the repo, chunks all files, embeds via kitai batch API, stores in FAISS.
Incremental: only re-embeds chunks whose content has changed (content_hash).

Mirrors rss_feed/enrich/embed_feeds.py exactly:
    collect_files → chunk → find_new(registry) → build_documents →
    kitai.batch embed → align → init_or_update FAISS → save_registry

Usage:
    python -m scripts.rag.embed_repo

Invariants:
    - guid = "{rel_path}::{chunk_index}" — stable per-chunk identifier
    - Registry written AFTER vectorstore — store failure leaves registry consistent
    - Dedup key: (guid, content_hash) — changed files get re-indexed automatically
    - data/vectorstore/repo/ holds FAISS index.faiss + index.pkl
    - data/rag_registry.tsv tracks: id, path, chunk_index, content_hash, guid
"""

import hashlib
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI

from kitai.batch import (
    build_embedding_tasks,
    download_batch_results,
    parse_embedding_results,
    poll_until_complete,
    submit_batch_job,
)
from kitai.index import create_vectorstore

ROOT             = Path(__file__).parent.parent.parent
VECTORSTORE_DIR  = ROOT / "data" / "vectorstore" / "repo"
REGISTRY_FILE    = ROOT / "data" / "rag_registry.tsv"

EMBED_MODEL      = "text-embedding-3-small"
EMBED_DIMENSIONS = 1536
POLL_INTERVAL    = 30  # seconds between batch status polls

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
    "wiki/**/*.py",
    "process/deltas/**/*.json",
    "CLAUDE.md",
    "README.md",
]

EXCLUDE_PARTS = {"__pycache__", ".git", "data", "venv", ".venv", "old"}
CHUNK_SIZE    = 400   # words per chunk
CHUNK_OVERLAP = 50    # overlap between consecutive chunks

REGISTRY_COLUMNS = ["id", "path", "chunk_index", "content_hash", "guid"]

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


# ── File collection ───────────────────────────────────────────────────────────

def collect_files() -> list[Path]:
    files: list[Path] = []
    for glob in INCLUDE_GLOBS:
        for p in ROOT.glob(glob):
            if p.is_file() and not any(part in EXCLUDE_PARTS for part in p.parts):
                files.append(p)
    result = sorted(set(files))
    log.info("Collected %d repo files.", len(result))
    return result


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    if not words:
        return [text] if text.strip() else []
    chunks: list[str] = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks or [text[:2000]]


# ── Registry ──────────────────────────────────────────────────────────────────

def load_registry() -> pd.DataFrame:
    if not REGISTRY_FILE.exists():
        log.info("Registry not found — cold start.")
        return pd.DataFrame(columns=REGISTRY_COLUMNS).astype({"id": int})
    df = pd.read_csv(REGISTRY_FILE, sep="\t", dtype={"id": int})
    log.info("Loaded registry: %d chunks.", len(df))
    return df


def save_registry(registry: pd.DataFrame) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_FILE.with_suffix(".tmp")
    registry.to_csv(tmp, sep="\t", index=False)
    tmp.replace(REGISTRY_FILE)
    log.info("Registry saved: %d chunks total.", len(registry))


# ── Chunk discovery ───────────────────────────────────────────────────────────

def build_all_chunks(files: list[Path]) -> list[dict]:
    all_chunks: list[dict] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = str(f.relative_to(ROOT))
        h   = _content_hash(text)
        for i, chunk in enumerate(_chunk_text(text)):
            all_chunks.append({
                "path":         rel,
                "chunk_index":  i,
                "content_hash": h,
                "guid":         f"{rel}::{i}",
                "text":         chunk,
            })
    log.info("Built %d total chunks.", len(all_chunks))
    return all_chunks


def find_new_chunks(all_chunks: list[dict], registry: pd.DataFrame) -> list[dict]:
    known: set[tuple[str, str]] = set()
    if not registry.empty:
        known = set(zip(registry["guid"], registry["content_hash"]))

    new = [c for c in all_chunks if (c["guid"], c["content_hash"]) not in known]
    log.info(
        "%d total | %d already indexed | %d new",
        len(all_chunks), len(known), len(new),
    )
    if not new:
        log.info("Nothing new to embed. Exiting.")
        sys.exit(0)
    return new


def assign_ids(new_chunks: list[dict], registry: pd.DataFrame) -> list[dict]:
    next_id = int(registry["id"].max()) + 1 if not registry.empty else 0
    for i, chunk in enumerate(new_chunks):
        chunk["id"] = next_id + i
    log.info("Assigned IDs %d–%d.", next_id, next_id + len(new_chunks) - 1)
    return new_chunks


# ── Document building ─────────────────────────────────────────────────────────

def build_documents(new_chunks: list[dict]) -> list[Document]:
    docs = [
        Document(
            page_content=c["text"],
            metadata={
                "id":           c["id"],
                "path":         c["path"],
                "chunk_index":  c["chunk_index"],
                "content_hash": c["content_hash"],
                "guid":         c["guid"],
            },
        )
        for c in new_chunks
    ]
    log.info("Built %d documents.", len(docs))
    return docs


# ── Embedding ─────────────────────────────────────────────────────────────────

def run_embedding_batch(
    docs: list[Document],
    client: OpenAI,
) -> list[tuple[str, list[float]]]:
    """Embed documents via kitai batch API (async, 50% cheaper than sync)."""
    tasks  = build_embedding_tasks(docs, model=EMBED_MODEL, dimensions=EMBED_DIMENSIONS)
    job_id = submit_batch_job(client, tasks)
    log.info("Batch submitted: %s (%d tasks)", job_id, len(tasks))

    completed = poll_until_complete(client, [job_id], poll_interval=POLL_INTERVAL)
    if job_id not in completed:
        raise RuntimeError(
            f"Batch {job_id} did not complete. Check OpenAI dashboard.\n"
            f"Resume: poll_until_complete(client, ['{job_id}'])"
        )

    results = download_batch_results(client, job_id)
    pairs   = parse_embedding_results(results)
    log.info("Parsed %d embeddings from batch %s.", len(pairs), job_id)
    return pairs


def align_pairs(
    pairs: list[tuple[str, list[float]]],
    docs: list[Document],
) -> tuple[list[tuple[str, list[float]]], list[Document]]:
    """Re-align pairs to doc order; drop any doc whose embedding is missing."""
    emb_by_id = {
        int(cid.removeprefix("custom_id_")): emb for cid, emb in pairs
    }
    aligned_pairs: list[tuple[str, list[float]]] = []
    aligned_docs:  list[Document] = []
    dropped = 0

    for doc in docs:
        doc_id = doc.metadata["id"]
        if doc_id in emb_by_id:
            aligned_pairs.append((doc.page_content, emb_by_id[doc_id]))
            aligned_docs.append(doc)
        else:
            log.warning("No embedding for id=%d (%s) — will retry next run.", doc_id, doc.metadata["guid"])
            dropped += 1

    if dropped:
        log.warning("%d doc(s) dropped — will be retried on next run.", dropped)
    log.info("Aligned %d document-embedding pairs.", len(aligned_docs))
    return aligned_pairs, aligned_docs


# ── Vectorstore ───────────────────────────────────────────────────────────────

def init_vectorstore(
    docs: list[Document],
    text_emb_pairs: list[tuple[str, list[float]]],
    embeddings_model: OpenAIEmbeddings,
) -> FAISS:
    embeddings_arr = np.array([emb for _, emb in text_emb_pairs], dtype=np.float32)
    store = create_vectorstore(docs, embeddings_arr, embeddings_model)
    log.info("Created vectorstore: %d vectors.", store.index.ntotal)
    return store


def update_vectorstore(
    text_emb_pairs: list[tuple[str, list[float]]],
    aligned_docs: list[Document],
    embeddings_model: OpenAIEmbeddings,
) -> FAISS:
    store = FAISS.load_local(
        str(VECTORSTORE_DIR), embeddings_model,
        allow_dangerous_deserialization=True,
    )
    before = store.index.ntotal
    store.add_embeddings(
        text_embeddings=text_emb_pairs,
        metadatas=[doc.metadata for doc in aligned_docs],
        ids=[doc.metadata["id"] for doc in aligned_docs],
    )
    log.info("Updated vectorstore: %d → %d (+%d).", before, store.index.ntotal, store.index.ntotal - before)
    return store


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    load_dotenv()

    if not os.environ.get("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY not set — nothing to embed. Exiting.")
        sys.exit(0)

    registry   = load_registry()
    files      = collect_files()
    all_chunks = build_all_chunks(files)
    new_chunks = find_new_chunks(all_chunks, registry)  # exits 0 if nothing new
    new_chunks = assign_ids(new_chunks, registry)
    docs       = build_documents(new_chunks)

    # Instantiate OpenAI clients only after confirming there is work to do.
    # kitai.batch handles bulk embedding (async, 50% cheaper than sync calls).
    # embeddings_model is stored in the FAISS pickle for single-query encoding at retrieval time.
    client           = OpenAI()
    embeddings_model = OpenAIEmbeddings(model=EMBED_MODEL, dimensions=EMBED_DIMENSIONS)

    pairs = run_embedding_batch(docs, client)

    aligned_pairs, aligned_docs = align_pairs(pairs, docs)
    if not aligned_docs:
        log.error("All embeddings failed — nothing to add. Exiting.")
        sys.exit(1)

    store_exists = VECTORSTORE_DIR.exists() and not registry.empty
    if store_exists:
        store = update_vectorstore(aligned_pairs, aligned_docs, embeddings_model)
    else:
        store = init_vectorstore(aligned_docs, aligned_pairs, embeddings_model)

    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(VECTORSTORE_DIR))
    log.info("Vectorstore saved → %s", VECTORSTORE_DIR)

    new_rows = pd.DataFrame([{
        "id":           doc.metadata["id"],
        "path":         doc.metadata["path"],
        "chunk_index":  doc.metadata["chunk_index"],
        "content_hash": doc.metadata["content_hash"],
        "guid":         doc.metadata["guid"],
    } for doc in aligned_docs])

    updated_registry = pd.concat([registry, new_rows], ignore_index=True)
    save_registry(updated_registry)
    log.info("[done] Indexed %d new chunks. Total in registry: %d.", len(aligned_docs), len(updated_registry))


if __name__ == "__main__":
    main()
