"""
Tests for the embedding index and retrieval system.
Run: pytest tests/test_retrieval.py -v
"""

import json
from pathlib import Path

import numpy as np
import pytest


class TestChunkText:
    def test_long_text_produces_multiple_chunks(self):
        from scripts.embed_index import chunk_text
        text = " ".join(f"word{i}" for i in range(1000))
        assert len(chunk_text(text, size=100, overlap=10)) > 1

    def test_all_chunks_non_empty(self):
        from scripts.embed_index import chunk_text
        chunks = chunk_text(" ".join(f"w{i}" for i in range(500)), size=100, overlap=10)
        assert all(c.strip() for c in chunks)

    def test_short_text_produces_one_chunk(self):
        from scripts.embed_index import chunk_text
        assert len(chunk_text("hello world")) == 1

    def test_chunks_overlap(self):
        from scripts.embed_index import chunk_text
        chunks = chunk_text(" ".join(f"w{i}" for i in range(200)), size=50, overlap=10)
        assert len(chunks) >= 2
        assert len(set(chunks[0].split()) & set(chunks[1].split())) > 0

    def test_empty_text_returns_empty(self):
        from scripts.embed_index import chunk_text
        chunks = chunk_text("")
        assert chunks == [] or all(not c.strip() for c in chunks)


class TestCollectFiles:
    def test_finds_python_scripts(self):
        from scripts.embed_index import collect_files
        assert any(f.suffix == ".py" for f in collect_files())

    def test_finds_markdown(self):
        from scripts.embed_index import collect_files
        assert any(f.suffix == ".md" for f in collect_files())

    def test_excludes_pycache(self):
        from scripts.embed_index import collect_files
        assert not any("__pycache__" in str(f) for f in collect_files())

    def test_excludes_data_dir(self):
        from scripts.embed_index import collect_files
        assert not any("/data/" in str(f) for f in collect_files())


class TestBuildChunks:
    def test_returns_list_of_dicts(self, tmp_path):
        from scripts.embed_index import build_chunks
        f = tmp_path / "test.py"
        f.write_text("def hello(): pass\n" * 50)
        chunks = build_chunks([f])
        assert len(chunks) >= 1
        assert all({"id", "source", "text", "file_type", "chunk_index"} <= set(c.keys()) for c in chunks)

    def test_chunk_ids_are_unique(self, tmp_path):
        from scripts.embed_index import build_chunks
        f = tmp_path / "big.py"
        f.write_text("word " * 1000)
        ids = [c["id"] for c in build_chunks([f])]
        assert len(ids) == len(set(ids))


class TestSaveAndLoadIndex:
    def test_save_creates_chunks_jsonl(self, tmp_path):
        from scripts.embed_index import save_index
        save_index([{"id": "a::0", "source": "a.py", "text": "hi", "file_type": "py", "chunk_index": 0}],
                   np.array([[0.1, 0.2]], dtype=np.float32), tmp_path)
        assert (tmp_path / "chunks.jsonl").exists()

    def test_round_trip_preserves_chunks(self, tmp_path):
        from scripts.embed_index import save_index
        chunks = [{"id": "x::0", "source": "x.py", "text": "rt", "file_type": "py", "chunk_index": 0}]
        save_index(chunks, np.array([[0.5, 0.5]], dtype=np.float32), tmp_path)
        loaded = [json.loads(l) for l in (tmp_path / "chunks.jsonl").read_text().splitlines()]
        assert loaded[0]["id"] == "x::0"


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        from scripts.retrieve import cosine_similarity
        q = np.array([1.0, 0.0], dtype=np.float32)
        assert abs(cosine_similarity(q, np.array([[1.0, 0.0]]))[0] - 1.0) < 1e-5

    def test_orthogonal_vectors_score_zero(self):
        from scripts.retrieve import cosine_similarity
        q = np.array([0.0, 1.0], dtype=np.float32)
        assert abs(cosine_similarity(q, np.array([[1.0, 0.0]]))[0]) < 1e-5

    def test_zero_vector_handled(self):
        from scripts.retrieve import cosine_similarity
        score = cosine_similarity(np.array([1.0, 0.0], dtype=np.float32), np.array([[0.0, 0.0]]))[0]
        assert np.isfinite(score)


class TestIndexNotFound:
    def test_raises_when_no_index(self, tmp_path, monkeypatch):
        from scripts import retrieve as rm
        monkeypatch.setattr(rm, "INDEX_DIR", tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError, match="Index not found"):
            rm.retrieve("query")


DIM = 6
VOCAB = {"stacy": 0, "intake": 1, "invoice": 2, "pdf": 3, "pricing": 4, "landing": 5}
MOCK_CHUNKS = [
    {"id": "agents::0",  "source": "agents/README.md",                   "text": "stacy intake agent classifies",     "file_type": "md",   "chunk_index": 0},
    {"id": "invoice::0", "source": "templates/pdf/invoice_standard.py", "text": "invoice pdf fpdf2 template render",  "file_type": "py",   "chunk_index": 0},
    {"id": "config::0",  "source": "config/global_settings.json",        "text": "pricing landing page 9.90 euros",    "file_type": "json", "chunk_index": 0},
]


def _bow(text):
    v = np.zeros(DIM, dtype=np.float32)
    for w in text.lower().split():
        if w in VOCAB: v[VOCAB[w]] += 1.0
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


MOCK_EMBEDDINGS = np.stack([_bow(c["text"]) for c in MOCK_CHUNKS])


class TestRetrievalIntegration:
    def _patch(self, mp):
        from scripts import retrieve as rm
        mp.setattr(rm, "load_index", lambda: (MOCK_CHUNKS, MOCK_EMBEDDINGS))
        mp.setattr(rm, "embed_query", lambda q, **kw: _bow(q))

    def test_top_result_for_invoice_query(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve
        assert retrieve("invoice pdf", top_k=3)[0]["source"] == "templates/pdf/invoice_standard.py"

    def test_top_result_for_agent_query(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve
        assert retrieve("stacy intake", top_k=3)[0]["source"] == "agents/README.md"

    def test_results_have_score_field(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve
        results = retrieve("pricing", top_k=2)
        assert all("score" in r and 0.0 <= r["score"] <= 1.01 for r in results)

    def test_top_k_limits_results(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve
        assert len(retrieve("anything", top_k=2)) == 2

    def test_results_sorted_descending(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve
        scores = [r["score"] for r in retrieve("invoice pdf", top_k=3)]
        assert scores == sorted(scores, reverse=True)
