"""Semantic classifier: sentence-transformers embeddings + persistent ChromaDB.

Each destination folder is described by a handful of example phrases. At startup the phrases are
embedded once and stored in a ChromaDB collection (cosine space). A document is classified by
embedding its text and taking the category whose examples are closest.

The embedder is injectable so tests run without torch; production uses `SentenceTransformerEmbedder`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

log = logging.getLogger("driverouter.classifier")

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION = "drive_categories"

# category key -> (destination path under the Drive root, example phrases).
# Override with CATEGORIES_FILE (JSON with the same shape) without touching code.
DEFAULT_CATEGORIES: dict[str, dict] = {
    "Banca": {
        "path": "01_Finanze_Legale/Banca",
        "examples": [
            "estratto conto bancario con saldo e movimenti del mese",
            "bonifico SEPA disposto, contabile di pagamento, IBAN beneficiario",
            "estratto conto carta di credito, addebiti e spese",
            "comunicazione della banca su conto corrente e interessi",
            "bank statement, account balance, transactions, credit card",
        ],
    },
    "Fisco_Tasse": {
        "path": "01_Finanze_Legale/Fisco_Tasse",
        "examples": [
            "modello F24 pagamento imposte e contributi",
            "dichiarazione dei redditi modello 730 o Redditi PF",
            "Agenzia delle Entrate avviso, cartella esattoriale, IMU, TARI",
            "certificazione unica CU, ritenute d'acconto, codice fiscale",
            "tax return, income tax, VAT, tax payment receipt",
        ],
    },
    "Contratti": {
        "path": "01_Finanze_Legale/Contratti",
        "examples": [
            "contratto di locazione tra locatore e conduttore, canone mensile",
            "contratto di fornitura luce gas, condizioni generali, firma delle parti",
            "accordo, clausole, recesso, durata del contratto, sottoscrizione",
            "polizza assicurativa, condizioni di polizza, premio annuo",
            "contract agreement between the parties, terms and conditions, signature",
        ],
    },
    "Lavoro": {
        "path": "02_Lavoro",
        "examples": [
            "busta paga cedolino stipendio mensile, retribuzione netta",
            "contratto di assunzione, lettera di assunzione, CCNL, mansione",
            "curriculum vitae, esperienze professionali, competenze",
            "TFR, ferie e permessi, comunicazione del datore di lavoro",
            "payslip, salary, employment contract, job offer",
        ],
    },
}


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Local, CPU-only embeddings. The model is loaded once and kept in memory."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        from sentence_transformers import SentenceTransformer  # heavy import, deferred

        self.name = model_name
        self._model = SentenceTransformer(model_name, device="cpu")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True, batch_size=16)
        return [v.tolist() for v in vectors]


@dataclass
class Classification:
    category: str | None  # None = below threshold, leave the file where it is
    path: str | None
    similarity: float  # cosine similarity of the best category, 0..1 for normalised vectors
    runner_up: str | None
    margin: float  # best - runner-up; small margin = ambiguous
    scores: dict[str, float]


def load_categories(path: str | None = None) -> dict[str, dict]:
    path = path or os.getenv("CATEGORIES_FILE")
    if not path:
        return DEFAULT_CATEGORIES
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    for key, cat in data.items():
        if not cat.get("path") or not cat.get("examples"):
            raise ValueError(f"category {key!r} needs 'path' and a non-empty 'examples' list")
    return data


def _fingerprint(categories: dict[str, dict], model_name: str) -> str:
    raw = json.dumps({"model": model_name, "categories": categories}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def chunk_text(text: str, chunk_chars: int = 1000, max_chunks: int = 3) -> list[str]:
    """MiniLM truncates at 256 word pieces, so embed a few leading chunks instead of one long blob."""
    text = " ".join(text.split())
    if not text:
        return []
    return [text[i : i + chunk_chars] for i in range(0, len(text), chunk_chars)][:max_chunks]


class SemanticClassifier:
    def __init__(
        self,
        embedder: Embedder,
        categories: dict[str, dict] | None = None,
        persist_dir: str | None = None,
        min_similarity: float | None = None,
        client_factory: Callable[[str], object] | None = None,
    ):
        import chromadb

        self.embedder = embedder
        self.categories = categories or load_categories()
        self.min_similarity = (
            float(os.getenv("MIN_SIMILARITY", "0.35")) if min_similarity is None else min_similarity
        )
        persist_dir = persist_dir or os.getenv("CHROMA_DIR", "/tmp/chroma")
        factory = client_factory or (lambda d: chromadb.PersistentClient(path=d))
        self._client = factory(persist_dir)
        self._collection = self._load_or_build()

    def _load_or_build(self):
        """Reuse the persisted index when categories and model are unchanged, otherwise rebuild it."""
        fp = _fingerprint(self.categories, self.embedder.name)
        try:
            existing = self._client.get_collection(COLLECTION)
            if (existing.metadata or {}).get("fingerprint") == fp:
                log.info("vectorstore reused", extra={"fingerprint": fp, "vectors": existing.count()})
                return existing
            self._client.delete_collection(COLLECTION)
        except Exception:  # collection missing: first start
            pass

        collection = self._client.create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine", "fingerprint": fp}
        )
        ids, docs, metas = [], [], []
        for key, cat in self.categories.items():
            for i, example in enumerate(cat["examples"]):
                ids.append(f"{key}:{i}")
                docs.append(example)
                metas.append({"category": key})
        collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=self.embedder.embed(docs))
        log.info("vectorstore built", extra={"fingerprint": fp, "vectors": len(ids)})
        return collection

    def classify(self, text: str) -> Classification:
        chunks = chunk_text(text)
        if not chunks:
            return Classification(None, None, 0.0, None, 0.0, {})

        n = min(self._collection.count(), 10)
        res = self._collection.query(
            query_embeddings=self.embedder.embed(chunks), n_results=n, include=["metadatas", "distances"]
        )
        # Score per category = best similarity across chunks and that category's examples.
        scores: dict[str, float] = {}
        for metas, dists in zip(res["metadatas"], res["distances"]):
            for meta, dist in zip(metas, dists):
                sim = 1.0 - float(dist)  # chroma cosine distance = 1 - cosine similarity
                cat = meta["category"]
                scores[cat] = max(scores.get(cat, -1.0), sim)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best, best_sim = ranked[0]
        runner_up, second = ranked[1] if len(ranked) > 1 else (None, 0.0)
        accepted = best_sim >= self.min_similarity
        return Classification(
            category=best if accepted else None,
            path=self.categories[best]["path"] if accepted else None,
            similarity=round(best_sim, 4),
            runner_up=runner_up,
            margin=round(best_sim - second, 4),
            scores={k: round(v, 4) for k, v in ranked},
        )
