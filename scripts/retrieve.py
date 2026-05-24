"""
retrieve.py — Thin wrapper. Delegates to scripts.rag.retrieve_repo.

The RAG Retriever agent (scripts/rag/retrieve_repo.py) is now the canonical
implementation: hybrid BM25 + FAISS, kitai.retriever, public ask() function.

Usage (unchanged — backward compatible):
    python -m scripts.retrieve "how does invoice generation work?"
    python -m scripts.retrieve "what agents are available?" --top-k 10 --json
"""

from scripts.rag.retrieve_repo import main

if __name__ == "__main__":
    main()
