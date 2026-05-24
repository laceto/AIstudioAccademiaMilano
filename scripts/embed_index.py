"""
embed_index.py — Thin wrapper. Delegates to scripts.rag.embed_repo.

The RAG Indexer agent (scripts/rag/embed_repo.py) is now the canonical
implementation: kitai batch API, FAISS vectorstore, incremental registry.

Usage (unchanged — backward compatible):
    python -m scripts.embed_index [--provider local|openai]
"""

from scripts.rag.embed_repo import main

if __name__ == "__main__":
    main()
