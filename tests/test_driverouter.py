"""Offline tests for driverouter (delivery 043): fake embedder, fake Drive, real ChromaDB."""
import hashlib
import math
import re

import pytest

chromadb = pytest.importorskip("chromadb")
pytest.importorskip("fastapi")

from driverouter import main as m  # noqa: E402
from driverouter.classifier import SemanticClassifier, chunk_text, load_categories  # noqa: E402


class BagOfWordsEmbedder:
    """Deterministic stand-in for MiniLM: hashed bag of words, L2-normalised."""

    name = "fake-bow"

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        out = []
        for t in texts:
            v = [0.0] * 512
            for w in re.findall(r"[a-zà-ù0-9]{3,}", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 512] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


@pytest.fixture
def classifier(tmp_path):
    return SemanticClassifier(BagOfWordsEmbedder(), persist_dir=str(tmp_path / "chroma"), min_similarity=0.2)


# ── classifier ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("Estratto conto: saldo finale e movimenti carta di credito", "Banca"),
    ("Modello F24 per il pagamento delle imposte, Agenzia delle Entrate", "Fisco_Tasse"),
    ("Contratto di locazione: il conduttore paga il canone mensile al locatore", "Contratti"),
    ("Cedolino busta paga: retribuzione netta e TFR", "Lavoro"),
])
def test_classifies_to_closest_category(classifier, text, expected):
    r = classifier.classify(text)
    assert r.category == expected
    assert r.path == load_categories()[expected]["path"]
    assert r.margin > 0


def test_unrelated_text_is_left_unsure(classifier):
    r = classifier.classify("zzz qqq xyzzy plugh")
    assert r.category is None and r.path is None


def test_empty_text_is_unsure(classifier):
    assert classifier.classify("   ").category is None


def test_index_is_reused_when_unchanged_and_rebuilt_when_categories_change(tmp_path):
    d = str(tmp_path / "chroma")
    first = BagOfWordsEmbedder()
    SemanticClassifier(first, persist_dir=d)
    assert first.calls == 1

    again = BagOfWordsEmbedder()
    SemanticClassifier(again, persist_dir=d)
    assert again.calls == 0  # persisted vectors reused, nothing re-embedded

    changed = BagOfWordsEmbedder()
    c = SemanticClassifier(changed, persist_dir=d, categories={"Medico": {"path": "03_Salute", "examples": ["referto visita medica"]}})
    assert changed.calls == 1
    assert c.classify("referto della visita medica").category == "Medico"


def test_categories_file_validation(tmp_path):
    bad = tmp_path / "c.json"
    bad.write_text('{"X": {"path": "A"}}')
    with pytest.raises(ValueError):
        load_categories(str(bad))


def test_chunk_text_limits_chunks():
    assert len(chunk_text("a " * 5000, chunk_chars=100, max_chunks=3)) == 3
    assert chunk_text("") == []


# ── naming ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("original,expected", [
    ("Estratto Conto Marzo.PDF", "2026-03-04_Banca_Estratto-Conto-Marzo.pdf"),
    ("20260101_scan 001.jpg", "2026-03-04_Banca_scan-001.jpg"),
    ("Nota spese è già pagata", "2026-03-04_Banca_Nota-spese-e-gia-pagata"),
    ("2026-03-04_Banca_Estratto.pdf", "2026-03-04_Banca_Estratto.pdf"),  # idempotent
    ("???.pdf", "2026-03-04_Banca_Documento.pdf"),
])
def test_clean_name(original, expected):
    assert m.clean_name(original, "Banca", "2026-03-04T10:00:00.000Z") == expected


# ── sync ──────────────────────────────────────────────────────────────────────

class FakeDrive:
    def __init__(self, files, folders):
        self.files = files
        self.folders = folders  # path -> id
        self.moves, self.marks, self.created = [], [], []

    def find_folder(self, path, create=False):
        if path not in self.folders and create:
            self.folders[path] = f"new-{path}"
            self.created.append(path)
        return self.folders.get(path)

    def list_inbox(self, inbox_id, limit):
        return self.files[:limit]

    def extract_text(self, f, inbox_id):
        if f.get("boom"):
            raise RuntimeError("download failed")
        return f.get("text", ""), "fake"

    def move(self, file_id, src, dest, new_name, props):
        self.moves.append((file_id, src, dest, new_name, props))

    def mark(self, file_id, props):
        self.marks.append((file_id, props))


FOLDERS = {"05_In_Arrivo_Da_Smistare": "inbox", "01_Finanze_Legale/Banca": "banca", "02_Lavoro": "lavoro"}


def _settings(**kw):
    s = m.Settings()
    s.inbox_id, s.inbox_path, s.dry_run, s.rename, s.max_files, s.create_missing = None, "05_In_Arrivo_Da_Smistare", False, True, 25, False
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_sync_moves_renames_and_marks(classifier):
    drive = FakeDrive([
        {"id": "1", "name": "doc1.pdf", "mimeType": "application/pdf", "createdTime": "2026-05-01T00:00:00Z",
         "text": "estratto conto saldo movimenti bonifico"},
        {"id": "2", "name": "foto.jpg", "mimeType": "image/jpeg", "text": "zzz qqq"},
        {"id": "3", "name": "old.pdf", "mimeType": "application/pdf", "appProperties": {"sr_status": "unsure"}},
        {"id": "4", "name": "_sr_tmp_x", "mimeType": "application/vnd.google-apps.document", "appProperties": {"sr_status": "tmp"}},
    ], dict(FOLDERS))
    out = m.sync_once(drive, classifier, _settings())
    assert (out["moved"], out["unsure"], out["skipped"], out["errors"]) == (1, 1, 2, 0)
    fid, src, dest, new_name, props = drive.moves[0]
    assert (fid, src, dest, new_name) == ("1", "inbox", "banca", "2026-05-01_Banca_doc1.pdf")
    assert props["sr_status"] == "routed" and props["sr_category"] == "Banca"
    assert drive.marks[0][0] == "2" and drive.marks[0][1]["sr_status"] == "unsure"


def test_dry_run_writes_nothing(classifier):
    drive = FakeDrive([{"id": "1", "name": "a.pdf", "mimeType": "application/pdf", "text": "busta paga cedolino stipendio"},
                       {"id": "2", "name": "b.pdf", "mimeType": "application/pdf", "text": "zzz"}], dict(FOLDERS))
    out = m.sync_once(drive, classifier, _settings(dry_run=True))
    assert out["moved"] == 1 and out["unsure"] == 1
    assert drive.moves == [] and drive.marks == []
    assert out["files"][0]["dest"] == "02_Lavoro"


def test_force_retries_unsure_files(classifier):
    drive = FakeDrive([{"id": "3", "name": "x.pdf", "mimeType": "application/pdf", "appProperties": {"sr_status": "unsure"},
                        "text": "busta paga stipendio"}], dict(FOLDERS))
    assert m.sync_once(drive, classifier, _settings(), force=True)["moved"] == 1


def test_missing_destination_is_an_error_unless_creation_enabled(classifier):
    files = [{"id": "1", "name": "f24.pdf", "mimeType": "application/pdf", "text": "modello F24 imposte Agenzia Entrate"}]
    drive = FakeDrive(list(files), dict(FOLDERS))
    out = m.sync_once(drive, classifier, _settings())
    assert out["errors"] == 1 and drive.moves == []

    drive = FakeDrive(list(files), dict(FOLDERS))
    assert m.sync_once(drive, classifier, _settings(create_missing=True))["moved"] == 1
    assert drive.created == ["01_Finanze_Legale/Fisco_Tasse"]


def test_one_bad_file_does_not_stop_the_run(classifier):
    drive = FakeDrive([{"id": "1", "name": "a.pdf", "mimeType": "application/pdf", "boom": True},
                       {"id": "2", "name": "b.pdf", "mimeType": "application/pdf", "text": "busta paga stipendio"}], dict(FOLDERS))
    out = m.sync_once(drive, classifier, _settings())
    assert out["errors"] == 1 and out["moved"] == 1


def test_missing_inbox_raises(classifier):
    with pytest.raises(RuntimeError):
        m.sync_once(FakeDrive([], {}), classifier, _settings())


# ── DriveClient against a recorded fake service ───────────────────────────────

class _Call:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeFiles:
    def __init__(self):
        self.calls = []

    def __getattr__(self, method):
        def call(**kw):
            self.calls.append((method, kw))
            if method == "list":
                return _Call({"files": [{"id": "id-" + kw["q"].split("'")[1]}]})
            if method == "copy":
                return _Call({"id": "tmp1"})
            if method == "export":
                return _Call(b"testo OCR")
            return _Call({"id": kw.get("fileId", "x")})
        return call


class FakeService:
    def __init__(self):
        self._files = FakeFiles()

    def files(self):
        return self._files


def test_drive_client_resolves_paths_moves_and_cleans_up_ocr_copy():
    svc = FakeService()
    dc = m.DriveClient(svc, _settings())
    assert dc.find_folder("01_Finanze_Legale/Banca") == "id-Banca"
    assert "'id-01_Finanze_Legale' in parents" in svc._files.calls[1][1]["q"]

    dc.move("f1", "inbox", "dest", "new.pdf", {"sr_status": "routed"})
    method, kw = svc._files.calls[-1]
    assert method == "update" and kw["addParents"] == "dest" and kw["removeParents"] == "inbox"
    assert kw["body"]["name"] == "new.pdf"

    text, how = dc.extract_text({"id": "img", "mimeType": "image/png", "name": "a.png"}, "inbox")
    assert (text, how) == ("testo OCR", "drive_ocr")
    assert [c[0] for c in svc._files.calls[-3:]] == ["copy", "export", "delete"]
    assert svc._files.calls[-1][1]["fileId"] == "tmp1"


def test_query_escaping():
    assert m._q("L'Agenzia") == "L\\'Agenzia"


# ── API ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch, classifier):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "0")
    monkeypatch.setenv("SYNC_API_KEY", "s3cret")
    m.runtime.classifier = classifier
    m.runtime.drive = FakeDrive([{"id": "1", "name": "a.pdf", "mimeType": "application/pdf",
                                  "text": "busta paga cedolino"}], dict(FOLDERS))
    with TestClient(m.app) as c:
        yield c
    m.runtime.classifier = m.runtime.drive = None


def test_sync_endpoint_requires_api_key(client):
    assert client.post("/sync-documents").status_code == 401
    assert client.post("/sync-documents", headers={"X-API-Key": "wrong"}).status_code == 401


def test_sync_endpoint_runs(client):
    r = client.post("/sync-documents", headers={"X-API-Key": "s3cret"})
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True  # DRY_RUN defaults to true
    assert body["moved"] == 1
    assert client.get("/health").json()["last_run"]["moved"] == 1


def test_sync_endpoint_fails_closed_without_key(client, monkeypatch):
    monkeypatch.delenv("SYNC_API_KEY")
    assert client.post("/sync-documents", headers={"X-API-Key": "x"}).status_code == 503


def test_sync_endpoint_rejects_overlap(client):
    m.runtime.lock.acquire()
    try:
        assert client.post("/sync-documents", headers={"X-API-Key": "s3cret"}).status_code == 409
    finally:
        m.runtime.lock.release()


def test_json_log_line_carries_extra_fields(capsys):
    import json
    import logging

    rec = logging.LogRecord("driverouter.x", logging.INFO, "f", 1, "file classified", None, None)
    rec.category, rec.similarity = "Banca", 0.81
    line = json.loads(m.JsonFormatter().format(rec))
    assert line["msg"] == "file classified" and line["category"] == "Banca" and line["similarity"] == 0.81
