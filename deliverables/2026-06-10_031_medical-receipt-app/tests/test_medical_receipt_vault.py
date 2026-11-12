"""Tests for Medical Receipt Vault (D031)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.constants import DEDUCTION_RATE, FRANCHISE_EUR, MAX_UPLOAD_BYTES
from app.crud import (
    available_years,
    create_receipt,
    delete_receipt,
    get_dashboard,
    get_receipt,
    get_tax_summary,
    list_receipts,
    update_receipt,
)
from app.database import Base
from app.export import to_excel, to_pdf_summary
from app.models import Receipt
from app.schemas import ReceiptCreate, ReceiptUpdate


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_receipt(**overrides) -> ReceiptCreate:
    defaults = dict(
        fiscal_year=2026,
        date="2026-03-15",
        provider_name="Farmacia Test",
        expense_type="farmaco",
        total_amount=20.0,
        deductible_amount=20.0,
        tax_deductible=True,
        status="confirmed",
    )
    defaults.update(overrides)
    return ReceiptCreate(**defaults)


# ─── CRUD round-trip ─────────────────────────────────────────────────────────

def test_create_and_get(db):
    r = create_receipt(db, _make_receipt())
    assert r.id is not None
    fetched = get_receipt(db, r.id)
    assert fetched.provider_name == "Farmacia Test"
    assert fetched.fiscal_year == 2026


def test_list_filters(db):
    create_receipt(db, _make_receipt(expense_type="farmaco", total_amount=10.0))
    create_receipt(db, _make_receipt(expense_type="visita", total_amount=80.0))
    all_r = list_receipts(db, fiscal_year=2026)
    assert len(all_r) == 2
    farmaci = list_receipts(db, fiscal_year=2026, expense_type="farmaco")
    assert len(farmaci) == 1
    assert float(farmaci[0].total_amount) == 10.0


def test_list_search(db):
    create_receipt(db, _make_receipt(provider_name="Farmacia Centrale"))
    create_receipt(db, _make_receipt(provider_name="Studio Dentistico Rossi"))
    result = list_receipts(db, search="Centrale")
    assert len(result) == 1
    assert "Centrale" in result[0].provider_name


def test_update_receipt(db):
    r = create_receipt(db, _make_receipt(status="pending_review"))
    updated = update_receipt(db, r.id, ReceiptUpdate(status="confirmed", provider_name="Farmacia Nuova"))
    assert updated.status == "confirmed"
    assert updated.provider_name == "Farmacia Nuova"


def test_delete_receipt(db):
    r = create_receipt(db, _make_receipt())
    assert delete_receipt(db, r.id) is True
    assert get_receipt(db, r.id) is None
    assert delete_receipt(db, "nonexistent") is False


def test_available_years(db):
    create_receipt(db, _make_receipt(fiscal_year=2024))
    create_receipt(db, _make_receipt(fiscal_year=2026))
    years = available_years(db)
    assert 2026 in years
    assert 2024 in years
    assert years[0] == 2026  # descending


# ─── dashboard / tax math ─────────────────────────────────────────────────────

def test_dashboard_basic(db):
    create_receipt(db, _make_receipt(total_amount=50.0, deductible_amount=50.0, tax_deductible=True))
    create_receipt(db, _make_receipt(total_amount=100.0, deductible_amount=100.0, tax_deductible=True))
    dash = get_dashboard(db, 2026)
    assert dash.total_receipts == 2
    assert dash.total_amount == 150.0
    assert dash.total_deductible == 150.0
    assert dash.pending_review == 0


def test_franchise_edge_below(db):
    """When deductible < franchise, saving must be 0."""
    create_receipt(db, _make_receipt(total_amount=50.0, deductible_amount=50.0, tax_deductible=True))
    dash = get_dashboard(db, 2026)
    assert dash.total_deductible == 50.0
    assert dash.estimated_tax_saving == 0.0  # 50 < 129.11


def test_franchise_edge_above(db):
    """Saving = 19% × (deductible - 129.11)."""
    create_receipt(db, _make_receipt(total_amount=300.0, deductible_amount=300.0, tax_deductible=True))
    dash = get_dashboard(db, 2026)
    expected = round((300.0 - FRANCHISE_EUR) * DEDUCTION_RATE, 2)
    assert dash.estimated_tax_saving == expected


def test_unknown_deductibility_excluded(db):
    """Receipts with tax_deductible=None must not count toward deductible total."""
    create_receipt(db, _make_receipt(total_amount=100.0, tax_deductible=None))
    dash = get_dashboard(db, 2026)
    assert dash.total_deductible == 0.0
    assert dash.unknown_deductibility == 1


def test_non_deductible_excluded(db):
    create_receipt(db, _make_receipt(total_amount=200.0, tax_deductible=False))
    dash = get_dashboard(db, 2026)
    assert dash.total_deductible == 0.0
    assert dash.estimated_tax_saving == 0.0


def test_pending_not_in_dashboard(db):
    create_receipt(db, _make_receipt(status="pending_review", total_amount=100.0))
    create_receipt(db, _make_receipt(status="confirmed", total_amount=50.0))
    dash = get_dashboard(db, 2026)
    assert dash.total_receipts == 1
    assert dash.pending_review == 1
    assert dash.total_amount == 50.0


def test_tax_summary_franchise(db):
    create_receipt(db, _make_receipt(total_amount=200.0, deductible_amount=200.0, tax_deductible=True))
    summary = get_tax_summary(db, 2026)
    assert summary.franchise_eur == FRANCHISE_EUR
    assert summary.taxable_base == round(200.0 - FRANCHISE_EUR, 2)
    assert summary.estimated_saving == round(summary.taxable_base * DEDUCTION_RATE, 2)


# ─── schema validation ────────────────────────────────────────────────────────

def test_invalid_date_rejected():
    with pytest.raises(Exception):
        ReceiptCreate(fiscal_year=2026, provider_name="X", date="15/03/2026")


def test_valid_date_accepted():
    r = ReceiptCreate(fiscal_year=2026, provider_name="X", date="2026-03-15")
    assert r.date == "2026-03-15"


def test_invalid_status_rejected():
    with pytest.raises(Exception):
        ReceiptCreate(fiscal_year=2026, provider_name="X", status="unknown_status")


def test_unknown_expense_type_normalised():
    r = ReceiptCreate(fiscal_year=2026, provider_name="X", expense_type="invalid_type")
    assert r.expense_type == "altro"


def test_receipt_create_default_status_pending():
    r = ReceiptCreate(fiscal_year=2026, provider_name="X")
    assert r.status == "pending_review"


# ─── export ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_receipts(db):
    receipts = [
        create_receipt(db, _make_receipt(total_amount=50.0, deductible_amount=50.0, expense_type="farmaco")),
        create_receipt(db, _make_receipt(total_amount=120.0, deductible_amount=120.0, expense_type="visita",
                                          provider_name="Dr. Rossi", date="2026-05-10")),
        create_receipt(db, _make_receipt(total_amount=30.0, tax_deductible=None, expense_type="altro")),
    ]
    return receipts


def test_excel_empty():
    xlsx = to_excel([], 2026)
    assert len(xlsx) > 0  # valid (but minimal) workbook


def test_excel_with_receipts(sample_receipts):
    xlsx = to_excel(sample_receipts, 2026)
    assert len(xlsx) > 1000


def test_pdf_empty():
    pdf = to_pdf_summary([], 2026)
    assert len(pdf) > 0
    assert pdf[:4] == b"%PDF"


def test_pdf_with_receipts(sample_receipts):
    pdf = to_pdf_summary(sample_receipts, 2026)
    assert len(pdf) > 1000
    assert pdf[:4] == b"%PDF"


# ─── storage validation ───────────────────────────────────────────────────────

def test_storage_size_limit(tmp_path):
    from app.storage import LocalStorageBackend
    backend = LocalStorageBackend(tmp_path / "uploads")
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ValueError, match="troppo grande"):
        backend.save(oversized, "test.jpg", 2026)


def test_storage_invalid_extension(tmp_path):
    from app.storage import LocalStorageBackend
    backend = LocalStorageBackend(tmp_path / "uploads")
    with pytest.raises(ValueError, match="non consentito"):
        backend.save(b"content", "malware.exe", 2026)


def test_storage_save_load_delete(tmp_path):
    from app.storage import LocalStorageBackend
    backend = LocalStorageBackend(tmp_path / "uploads")
    path, ftype = backend.save(b"test image data", "photo.jpg", 2026)
    assert ftype == "image"
    loaded = backend.load(path)
    assert loaded == b"test image data"
    backend.delete(path)
    assert backend.load(path) is None


# ─── extractor ───────────────────────────────────────────────────────────────

def test_extract_no_api_key(monkeypatch):
    from app.extractor import extract_from_image
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = extract_from_image(b"fake image")
    assert result.confidence == 0.0


def test_extract_json_decode_error(monkeypatch):
    from app.extractor import extract_from_image
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "not valid json {{{{"
    with patch("app.extractor.OpenAI", return_value=mock_client):
        result = extract_from_image(b"fake image")
    assert result.confidence == 0.0


def test_extract_happy_path(monkeypatch):
    from app.extractor import extract_from_image
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    payload = {
        "date": "2026-03-15",
        "receipt_number": "SF001",
        "provider_name": "Farmacia Centrale",
        "provider_tax_id": "01234567890",
        "expense_type": "farmaco",
        "description": "Amoxicillina 875mg",
        "payment_method": "Carta di debito",
        "total_amount": 8.50,
        "deductible_amount": 8.50,
        "tax_deductible": True,
        "line_items": [{"description": "Amoxicillina", "quantity": 1, "unit_price": 8.50, "total": 8.50}],
        "confidence": 0.95,
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = json.dumps(payload)
    with patch("app.extractor.OpenAI", return_value=mock_client):
        result = extract_from_image(b"fake image")
    assert result.confidence == 0.95
    assert result.provider_name == "Farmacia Centrale"
    assert result.total_amount == 8.50
    assert result.tax_deductible is True
    assert len(result.line_items) == 1


def test_extract_null_deductibility_preserved(monkeypatch):
    """null tax_deductible from model must become None, not True."""
    from app.extractor import extract_from_image
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    payload = {"provider_name": "Farmacia X", "total_amount": 5.0, "tax_deductible": None, "confidence": 0.6}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = json.dumps(payload)
    with patch("app.extractor.OpenAI", return_value=mock_client):
        result = extract_from_image(b"fake image")
    assert result.tax_deductible is None


def test_extract_api_error_propagates(monkeypatch):
    """OpenAI API errors must propagate — not be silently swallowed."""
    from app.extractor import extract_from_image
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("simulated API error")
    with patch("app.extractor.OpenAI", return_value=mock_client):
        with pytest.raises(RuntimeError, match="simulated API error"):
            extract_from_image(b"fake image")


# ─── API (FastAPI TestClient) ─────────────────────────────────────────────────

@pytest.fixture
def api_client(tmp_path):
    from fastapi.testclient import TestClient
    import api as api_module
    from app.database import get_db

    engine_mem = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine_mem)
    TestSession = sessionmaker(bind=engine_mem)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    api_module.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(api_module.app)
    yield client
    api_module.app.dependency_overrides.clear()


def test_api_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["db"] is True


def test_api_upload_too_large(api_client):
    big = b"x" * (MAX_UPLOAD_BYTES + 1)
    r = api_client.post(
        "/receipts/upload",
        data={"fiscal_year": 2026, "auto_extract": "false"},
        files={"file": ("big.jpg", big, "image/jpeg")},
    )
    assert r.status_code == 413


def test_api_upload_invalid_extension(api_client):
    r = api_client.post(
        "/receipts/upload",
        data={"fiscal_year": 2026, "auto_extract": "false"},
        files={"file": ("malware.exe", b"content", "application/octet-stream")},
    )
    assert r.status_code == 415


@pytest.fixture
def api_client_with_storage(api_client, tmp_path):
    import app.storage as storage_mod
    from app.storage import LocalStorageBackend
    original = storage_mod._default_backend
    storage_mod._default_backend = LocalStorageBackend(tmp_path / "uploads")
    yield api_client
    storage_mod._default_backend = original


def test_api_delete_order(api_client_with_storage):
    """File should be deleted AFTER the DB row — verify DB row is gone even if file missing."""
    r = api_client_with_storage.post(
        "/receipts/upload",
        data={"fiscal_year": 2026, "auto_extract": "false"},
        files={"file": ("photo.jpg", b"\xff\xd8\xff" + b"x" * 10, "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    receipt_id = r.json()["id"]

    del_r = api_client_with_storage.delete(f"/receipts/{receipt_id}")
    assert del_r.status_code == 204

    get_r = api_client_with_storage.get(f"/receipts/{receipt_id}")
    assert get_r.status_code == 404


def test_api_confirm_endpoint(api_client_with_storage):
    r = api_client_with_storage.post(
        "/receipts/upload",
        data={"fiscal_year": 2026, "auto_extract": "false"},
        files={"file": ("photo.jpg", b"\xff\xd8\xff" + b"x" * 10, "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    receipt_id = r.json()["id"]
    assert r.json()["status"] == "pending_review"

    conf_r = api_client_with_storage.post(f"/receipts/{receipt_id}/confirm")
    assert conf_r.status_code == 200
    assert conf_r.json()["status"] == "confirmed"


def test_api_export_summary_json(api_client):
    r = api_client.get("/export/summary/2026")
    assert r.status_code == 200
    data = r.json()
    assert "franchise_eur" in data
    assert data["franchise_eur"] == FRANCHISE_EUR
