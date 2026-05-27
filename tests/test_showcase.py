"""Tests for gateway.showcase — audit-log → showcase card builder."""

from pathlib import Path

import pytest

from gateway.showcase import ShowcaseCard, load_cards, parse_audit


FIXTURES = Path(__file__).parent / "fixtures" / "audit"


@pytest.fixture
def fixture_dir(tmp_path: Path) -> Path:
    """Build an isolated audit dir with a representative spread of YAML logs."""
    d = tmp_path / "audit"
    d.mkdir()

    (d / "2026-05-26_022_family-archivist.md").write_text(
        "# Audit Log — Request 022\n\n```yaml\n"
        'request_id: "022"\n'
        'date: "2026-05-26"\n'
        "intent: family_archivist\n"
        "product_type: family_archivist\n"
        "outcome: success\n"
        "```\n",
        encoding="utf-8",
    )

    (d / "2026-05-24_014_dispenser-input.md").write_text(
        "# Audit Log — Request 014\n\n```yaml\n"
        'request_id: "014"\n'
        'date: "2026-05-24"\n'
        "intent: dispenser_input\n"
        "product_type: internal_infra_build\n"
        "outcome: success\n"
        "```\n",
        encoding="utf-8",
    )

    (d / "2026-05-24_016_iss005-bugfix.md").write_text(
        "# Audit Log — Request 016\n\n```yaml\n"
        'request_id: "016"\n'
        'date: "2026-05-24"\n'
        "intent: internal_bugfix\n"
        "product_type: internal_infra_build\n"
        "outcome: success_internal_rd\n"
        "```\n",
        encoding="utf-8",
    )

    (d / "2026-05-23_001_bakery-website.md").write_text(
        "# Audit Log — Request 001\n\n```yaml\n"
        'request_id: "001"\n'
        'date: "2026-05-23"\n'
        "intent: website_creation\n"
        "product_type: static_landing_page\n"
        "outcome: success\n"
        "```\n",
        encoding="utf-8",
    )

    (d / "2026-05-23_999_failed-attempt.md").write_text(
        "# Audit Log — Request 999\n\n```yaml\n"
        'request_id: "999"\n'
        'date: "2026-05-23"\n'
        "intent: experiment\n"
        "product_type: static_landing_page\n"
        "outcome: failed\n"
        "```\n",
        encoding="utf-8",
    )

    (d / "README.md").write_text("not an audit log\n", encoding="utf-8")
    return d


def test_parse_audit_extracts_yaml_block(fixture_dir: Path) -> None:
    audit = parse_audit(fixture_dir / "2026-05-26_022_family-archivist.md")
    assert audit is not None
    assert audit["request_id"] == "022"
    assert audit["product_type"] == "family_archivist"


def test_parse_audit_returns_none_for_non_audit(fixture_dir: Path) -> None:
    assert parse_audit(fixture_dir / "README.md") is None


def test_load_cards_filters_failed_outcomes(fixture_dir: Path) -> None:
    cards = load_cards(audit_dir=fixture_dir)
    ids = [c.request_id for c in cards]
    assert "999" not in ids, "failed outcomes must not surface"


def test_load_cards_filters_internal_infra(fixture_dir: Path) -> None:
    cards = load_cards(audit_dir=fixture_dir)
    ids = [c.request_id for c in cards]
    assert "014" not in ids, "internal_infra_build is unpriced — must be hidden"
    assert "016" not in ids


def test_load_cards_keeps_priced_successes(fixture_dir: Path) -> None:
    cards = load_cards(audit_dir=fixture_dir)
    ids = [c.request_id for c in cards]
    assert "022" in ids
    assert "001" in ids


def test_load_cards_sorted_by_date_descending(fixture_dir: Path) -> None:
    cards = load_cards(audit_dir=fixture_dir)
    dates = [c.date for c in cards]
    assert dates == sorted(dates, reverse=True)


def test_card_carries_price_from_product_type(fixture_dir: Path) -> None:
    cards = load_cards(audit_dir=fixture_dir)
    by_id = {c.request_id: c for c in cards}
    assert by_id["022"].price_eur == 14.90  # family_archivist
    assert by_id["001"].price_eur == 9.90   # static_landing_page


def test_card_has_human_title(fixture_dir: Path) -> None:
    cards = load_cards(audit_dir=fixture_dir)
    by_id = {c.request_id: c for c in cards}
    assert by_id["001"].title == "Static Landing Page"
    assert by_id["022"].title == "Family Archivist"


def test_load_cards_real_audit_dir_does_not_crash() -> None:
    """Smoke test against the live process/audit/ — must not raise."""
    repo_audit = Path(__file__).resolve().parents[1] / "process" / "audit"
    if not repo_audit.exists():
        pytest.skip("process/audit/ not present")
    cards = load_cards(audit_dir=repo_audit)
    assert isinstance(cards, list)
    for c in cards:
        assert isinstance(c, ShowcaseCard)
        assert c.price_eur is not None and c.price_eur > 0
