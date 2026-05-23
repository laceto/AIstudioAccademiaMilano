"""
Tests for the embedding index and retrieval system (ISS-008).

Run: pytest tests/test_retrieval.py -v
"""

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parent.parent


# ——— embed_index: chunk_text ————————————————————————————————————————————————

class TestChunkText:
    def test_long_text_produces_multiple_chunks(self):
        from scripts.embed_index import chunk_text

        text = " ".join(f"word{i}" for i in range(1000))
        chunks = chunk_text(text, size=100, overlap=10)
        assert len(chunks) > 1

    def test_all_chunks_non_empty(self):
        from scripts.embed_index import chunk_text

        text = " ".join(f"word{i}" for i in range(500))
        chunks = chunk_text(text, size=100, overlap=10)
        assert all(c.strip() for c in chunks)

    def test_short_text_produces_one_chunk(self):
        from scripts.embed_index import chunk_text

        chunks = chunk_text("hello world")
        assert len(chunks) == 1

    def test_chunks_overlap(self):
        from scripts.embed_index import chunk_text

        text = " ".join(f"w{i}" for i in range(200))
        chunks = chunk_text(text, size=50, overlap=10)
        assert len(chunks) >= 2
        c1_words = set(chunks[0].split())
        c2_words = set(chunks[1].split())
        # overlap means some words from end of chunk 1 appear in start of chunk 2
        assert len(c1_words & c2_words) > 0

    def test_empty_text_returns_empty(self):
        from scripts.embed_index import chunk_text

        chunks = chunk_text("")
        assert chunks == [] or all(not c.strip() for c in chunks)


# ——— embed_index: collect_files ——————————————————————————————————————————————

class TestCollectFiles:
    def test_finds_python_scripts(self):
        from scripts.embed_index import collect_files

        files = collect_files()
        assert any(f.suffix == ".py" for f in files)

    def test_finds_markdown(self):
        from scripts.embed_index import collect_files

        files = collect_files()
        assert any(f.suffix == ".md" for f in files)

    def test_excludes_pycache(self):
        from scripts.embed_index import collect_files

        files = collect_files()
        assert not any("__pycache__" in str(f) for f in files)

    def test_excludes_data_dir(self):
        from scripts.embed_index import collect_files

        files = collect_files()
        assert not any("/data/" in str(f) for f in files)


# ——— embed_index: build_chunks ——————————————————————————————————————————————

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
        chunks = build_chunks([f])
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_source_field_is_relative_path(self, tmp_path):
        from scripts import embed_index as ei

        f = tmp_path / "sample.md"
        f.write_text("# Hello\nContent here.")
        # Temporarily override ROOT
        original_root = ei.ROOT
        ei.ROOT = tmp_path
        try:
            chunks = ei.build_chunks([f])
            assert not any(c["source"].startswith("/") for c in chunks)
        finally:
            ei.ROOT = original_root


# ——— embed_index: save_index ——————————————————————————————————————————————

class TestSaveAndLoadIndex:
    def test_save_creates_chunks_jsonl(self, tmp_path):
        from scripts.embed_index import save_index

        chunks = [{"id": "a::0", "source": "a.py", "text": "hello", "file_type": "py", "chunk_index": 0}]
        embeddings = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        save_index(chunks, embeddings, tmp_path)
        assert (tmp_path / "chunks.jsonl").exists()

    def test_save_creates_embeddings_npy(self, tmp_path):
        from scripts.embed_index import save_index

        chunks = [{"id": "a::0", "source": "a.py", "text": "hello", "file_type": "py", "chunk_index": 0}]
        embeddings = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        save_index(chunks, embeddings, tmp_path)
        assert (tmp_path / "embeddings.npy").exists()

    def test_round_trip_preserves_chunks(self, tmp_path):
        from scripts.embed_index import save_index

        chunks = [{"id": "x::0", "source": "x.py", "text": "round trip", "file_type": "py", "chunk_index": 0}]
        embeddings = np.array([[0.5, 0.5]], dtype=np.float32)
        save_index(chunks, embeddings, tmp_path)
        loaded = [json.loads(l) for l in (tmp_path / "chunks.jsonl").read_text().splitlines()]
        assert loaded[0]["id"] == "x::0"

    def test_round_trip_preserves_embeddings(self, tmp_path):
        from scripts.embed_index import save_index

        chunks = [{"id": "y::0", "source": "y.py", "text": "embed", "file_type": "py", "chunk_index": 0}]
        orig = np.array([[0.1, 0.9]], dtype=np.float32)
        save_index(chunks, orig, tmp_path)
        loaded = np.load(str(tmp_path / "embeddings.npy"))
        assert np.allclose(loaded, orig)


# ——— retrieve: cosine_similarity ———————————————————————————————————————————

class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        from scripts.retrieve import cosine_similarity

        corpus = np.array([[1.0, 0.0]], dtype=np.float32)
        query = np.array([1.0, 0.0], dtype=np.float32)
        assert abs(cosine_similarity(query, corpus)[0] - 1.0) < 1e-5

    def test_opposite_vectors_score_minus_one(self):
        from scripts.retrieve import cosine_similarity

        corpus = np.array([[1.0, 0.0]], dtype=np.float32)
        query = np.array([-1.0, 0.0], dtype=np.float32)
        assert abs(cosine_similarity(query, corpus)[0] + 1.0) < 1e-5

    def test_orthogonal_vectors_score_zero(self):
        from scripts.retrieve import cosine_similarity

        corpus = np.array([[1.0, 0.0]], dtype=np.float32)
        query = np.array([0.0, 1.0], dtype=np.float32)
        assert abs(cosine_similarity(query, corpus)[0]) < 1e-5

    def test_zero_vector_handled(self):
        from scripts.retrieve import cosine_similarity

        corpus = np.array([[0.0, 0.0]], dtype=np.float32)
        query = np.array([1.0, 0.0], dtype=np.float32)
        score = cosine_similarity(query, corpus)[0]
        assert np.isfinite(score)


# ——— retrieve: index not found ————————————————————————————————————————————

class TestIndexNotFound:
    def test_raises_when_no_index(self, tmp_path, monkeypatch):
        from scripts import retrieve as retrieve_module

        monkeypatch.setattr(retrieve_module, "INDEX_DIR", tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError, match="Index not found"):
            retrieve_module.retrieve("some query")


# ——— retrieve: integration with mock index ———————————————————————————————

DIM = 6
VOCAB = {"stacy": 0, "intake": 1, "invoice": 2, "pdf": 3, "pricing": 4, "landing": 5}

MOCK_CHUNKS = [
    {"id": "agents::0",   "source": "agents/README.md",                    "text": "stacy intake agent classifies user requests",   "file_type": "md",   "chunk_index": 0},
    {"id": "invoice::0",  "source": "templates/pdf/invoice_standard.py",  "text": "invoice pdf fpdf2 template render",             "file_type": "py",   "chunk_index": 0},
    {"id": "config::0",   "source": "config/global_settings.json",         "text": "pricing landing page 9.90 euros static",         "file_type": "json", "chunk_index": 0},
]


def _bow(text: str) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    for word in text.lower().split():
        if word in VOCAB:
            v[VOCAB[word]] += 1.0
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


MOCK_EMBEDDINGS = np.stack([_bow(c["text"]) for c in MOCK_CHUNKS])


class TestRetrievalIntegration:
    def _patch(self, monkeypatch):
        from scripts import retrieve as rm

        monkeypatch.setattr(rm, "load_index", lambda: (MOCK_CHUNKS, MOCK_EMBEDDINGS))
        monkeypatch.setattr(rm, "embed_query", lambda q, **kw: _bow(q))

    def test_top_result_for_invoice_query(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve

        results = retrieve("invoice pdf", top_k=3)
        assert results[0]["source"] == "templates/pdf/invoice_standard.py"

    def test_top_result_for_agent_query(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve

        results = retrieve("stacy intake", top_k=3)
        assert results[0]["source"] == "agents/README.md"

    def test_results_have_score_field(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve

        results = retrieve("pricing landing", top_k=2)
        assert all("score" in r for r in results)
        assert all(0.0 <= r["score"] <= 1.01 for r in results)

    def test_top_k_limits_results(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve

        results = retrieve("anything", top_k=2)
        assert len(results) == 2

    def test_results_sorted_by_score_descending(self, monkeypatch):
        self._patch(monkeypatch)
        from scripts.retrieve import retrieve

        results = retrieve("invoice pdf", top_k=3)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
