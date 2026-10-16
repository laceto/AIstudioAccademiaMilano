"""Offline tests for bankanalyst (delivery 045): synthetic Credem and ING statements built with fpdf2."""
from datetime import date
from decimal import Decimal

import pytest

pytest.importorskip("pdfplumber")
fpdf = pytest.importorskip("fpdf")
openpyxl = pytest.importorskip("openpyxl")

from bankanalyst.amounts import parse_amount, parse_date  # noqa: E402
from bankanalyst.classify import Classifier, load_rules  # noqa: E402
from bankanalyst.models import Transaction  # noqa: E402
from bankanalyst.parse import parse_statement  # noqa: E402
from bankanalyst.report import analyze, dedupe, quarter_of, write_excel  # noqa: E402


# ── synthetic statements ──────────────────────────────────────────────────────

def _pdf(path, header_lines, columns, rows, footer_lines):
    """columns: [(title, x, width, align)]; rows: list of cell lists (None = empty), or str = continuation."""
    pdf = fpdf.FPDF(orientation="L")
    pdf.add_page()
    pdf.set_font("Helvetica", size=9)
    for line in header_lines:
        pdf.set_x(10)
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    y = pdf.get_y()
    for title, x, w, align in columns:
        pdf.set_xy(x, y)
        pdf.cell(w, 6, title, align=align)
    pdf.ln(7)
    for row in rows:
        y = pdf.get_y()
        if isinstance(row, str):  # continuation of the description
            desc_col = next(c for c in columns if c[0].lower().startswith("descr"))
            pdf.set_xy(desc_col[1], y)
            pdf.cell(desc_col[2], 5, row)
        else:
            for (title, x, w, align), value in zip(columns, row):
                if value:
                    pdf.set_xy(x, y)
                    pdf.cell(w, 5, value, align=align)
        pdf.ln(5)
    pdf.ln(3)
    for line in footer_lines:
        pdf.set_x(10)
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))
    return path


def make_ing(path, closing="2.580,81"):
    cols = [("Data contabile", 10, 28, "L"), ("Data valuta", 40, 28, "L"),
            ("Uscite", 70, 25, "R"), ("Entrate", 97, 25, "R"),
            ("Causale", 125, 40, "L"), ("Descrizione operazione", 167, 120, "L")]
    rows = [
        ["02/01/2026", "02/01/2026", "54,30", None, "PAGAMENTO CARTA", "ESSELUNGA MILANO VIALE PIAVE"],
        ["10/01/2026", "10/01/2026", None, "2.150,00", "ACCREDITO BONIFICO", "Stipendio ACME SRL"],
        "mese di dicembre",
        ["15/02/2026", "15/02/2026", "12,99", None, "PAGAMENTO CARTA", "NETFLIX.COM"],
        ["20/03/2026", "20/03/2026", "500,00", None, "GIROCONTO", "Giroconto verso conto Credem"],
        ["30/03/2026", "31/03/2026", "1,90", None, "COMMISSIONI", "Canone mensile"],
    ]
    return _pdf(path, ["ING Bank N.V. - Milan Branch", "Conto Corrente Arancio - Estratto conto",
                       "Saldo iniziale 1.000,00"], cols, rows,
                ["Totale uscite 569,19   Totale entrate 2.150,00", f"Saldo finale {closing}", "Pagina 1 di 1"])


def make_credem(path):
    cols = [("Data", 10, 25, "L"), ("Valuta", 37, 25, "L"),
            ("Dare", 64, 25, "R"), ("Avere", 91, 25, "R"),
            ("Descrizione operazioni", 120, 160, "L")]
    rows = [
        ["03/04/2026", "03/04/2026", "62,00", None, "PAGAMENTO POS ENI STATION 1234"],
        ["21/04/2026", "21/04/2026", None, "500,00", "BONIFICO DA ING BANK giroconto"],
        ["05/05/2026", "05/05/2026", "88,40", None, "ADDEBITO SDD ENEL ENERGIA"],
        "bolletta luce aprile",
        ["12/07/2026", "12/07/2026", "250,00", None, "PRELIEVO BANCOMAT ATM CREDEM"],
        ["18/07/2026", "18/07/2026", "37,20", None, "PAGAMENTO POS MISTERO SNC"],
    ]
    return _pdf(path, ["CREDEM - Credito Emiliano S.p.A.", "Estratto conto corrente",
                       "Saldo iniziale 2.000,00"], cols, rows, ["Saldo finale 2.062,40"])


@pytest.fixture
def pdf_dir(tmp_path):
    d = tmp_path / "estratti"
    d.mkdir()
    make_ing(d / "ing_q1.pdf")
    make_credem(d / "credem_q2q3.pdf")
    return d


@pytest.fixture
def statements(pdf_dir):
    return [parse_statement(p) for p in sorted(pdf_dir.glob("*.pdf"))]


# ── amounts / dates ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("1.234,56", Decimal("1234.56")), ("54,30", Decimal("54.30")), ("1.234,56-", Decimal("-1234.56")),
    ("-12,00", Decimal("-12.00")), ("€ 9,90", Decimal("9.90")), ("+3,00", Decimal("3.00")),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["2026", "12.34", "abc", "1,2", "01/02/2026"])
def test_parse_amount_rejects(raw):
    assert parse_amount(raw) is None


def test_parse_date():
    assert parse_date("02/01/2026") == date(2026, 1, 2)
    assert parse_date("02.01.26") == date(2026, 1, 2)
    assert parse_date("31/02/2026") is None
    assert parse_date("54,30") is None


# ── parsing ───────────────────────────────────────────────────────────────────

def test_parse_ing(tmp_path):
    st = parse_statement(make_ing(tmp_path / "ing.pdf"))
    assert st.bank == "ing"
    assert [t.amount for t in st.transactions] == [
        Decimal("-54.30"), Decimal("2150.00"), Decimal("-12.99"), Decimal("-500.00"), Decimal("-1.90")]
    assert st.transactions[1].description.endswith("mese di dicembre")
    assert st.transactions[0].booking_date == date(2026, 1, 2)
    assert st.transactions[4].value_date == date(2026, 3, 31)
    assert "PAGAMENTO CARTA" in st.transactions[0].description
    assert st.opening == Decimal("1000.00") and st.closing == Decimal("2580.81")
    assert st.reconciliation() == "ok"
    assert not any(t.sign_uncertain for t in st.transactions)


def test_parse_credem(tmp_path):
    st = parse_statement(make_credem(tmp_path / "credem.pdf"))
    assert st.bank == "credem"
    assert len(st.transactions) == 5
    assert st.transactions[1].amount == Decimal("500.00")
    assert "bolletta luce aprile" in st.transactions[2].description
    assert st.reconciliation() == "ok"


def test_reconciliation_flags_mismatch(tmp_path):
    st = parse_statement(make_ing(tmp_path / "ing.pdf", closing="1.800,00"))
    assert st.reconciliation().startswith("diff")


def test_generic_without_columns_marks_sign_uncertain(tmp_path):
    p = tmp_path / "other.pdf"
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    for line in ["Banca Qualunque", "05/06/2026 Pagamento POS BAR CENTRALE 3,50",
                 "07/06/2026 Accredito bonifico stipendio 1.000,00", "08/06/2026 Rimborso spese 20,00-"]:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(p))
    st = parse_statement(p)
    assert st.bank == "generic"
    assert [t.amount for t in st.transactions] == [Decimal("-3.50"), Decimal("1000.00"), Decimal("-20.00")]
    assert [t.sign_uncertain for t in st.transactions] == [True, True, False]
    assert st.reconciliation() == "n.d."


# ── classification ────────────────────────────────────────────────────────────

def _tx(desc, amount):
    return Transaction(bank="ing", booking_date=date(2026, 1, 1), value_date=None,
                       description=desc, amount=Decimal(amount), source="x.pdf", page=1)


def test_classifier_default_rules():
    c = Classifier(load_rules())
    assert c.classify(_tx("PAGAMENTO CARTA ESSELUNGA", "-10")) == "Spesa alimentare"
    assert c.classify(_tx("Stipendio ACME SRL", "2000")) == "Stipendio e redditi"
    assert c.classify(_tx("Giroconto verso conto Credem", "-500")) == "Giroconti tra conti"
    assert c.classify(_tx("PRELIEVO BANCOMAT ATM", "-50")) == "Prelievi contanti"
    assert c.classify(_tx("NETFLIX.COM", "-12.99")) == "Abbonamenti e digitale"
    assert c.classify(_tx("PAGAMENTO POS MISTERO SNC", "-1")) == "Da classificare"


def test_rule_direction_and_custom_file(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "categories:\n"
        "  - name: Rimborsi\n    direction: in\n    patterns: ['rimborso']\n"
        "  - name: Spese mediche\n    patterns: ['rimborso', 'farmacia']\n", encoding="utf-8")
    c = Classifier(load_rules(rules))
    assert c.classify(_tx("Rimborso ticket", "30")) == "Rimborsi"
    assert c.classify(_tx("Rimborso ticket", "-30")) == "Spese mediche"


def test_overrides_win(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text("overrides:\n  'MISTERO SNC': Ristoranti e bar\ncategories: []\n", encoding="utf-8")
    c = Classifier(load_rules(rules))
    assert c.classify(_tx("PAGAMENTO POS MISTERO SNC", "-1")) == "Ristoranti e bar"


# ── report ────────────────────────────────────────────────────────────────────

def test_quarter_of():
    assert quarter_of(date(2026, 1, 1)) == "2026-Q1"
    assert quarter_of(date(2026, 12, 31)) == "2026-Q4"


def test_dedupe_overlapping_statements(tmp_path):
    a = parse_statement(make_ing(tmp_path / "a.pdf"))
    b = parse_statement(make_ing(tmp_path / "b.pdf"))
    assert len(dedupe(a.transactions + b.transactions)) == len(a.transactions)


def test_analyze_quarters_and_transfers(statements):
    res = analyze(statements)
    assert set(res.quarters) == {"2026-Q1", "2026-Q2", "2026-Q3"}
    q1 = res.totals["2026-Q1"]
    # Transfers between own accounts are excluded from income and spending.
    assert q1["entrate"] == Decimal("2150.00")
    assert q1["uscite"] == Decimal("-69.19")
    assert res.totals["2026-Q2"]["entrate"] == Decimal("0")
    assert res.pivot["Giroconti tra conti"]["2026-Q1"] == Decimal("-500.00")
    assert len(res.unclassified) == 1
    assert all(c["esito"] == "ok" for c in res.checks)


def test_write_excel(statements, tmp_path):
    out = write_excel(analyze(statements), tmp_path / "report.xlsx")
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Riepilogo", "Per categoria", "Movimenti", "Da classificare", "Controlli"]
    mov = wb["Movimenti"]
    assert mov.max_row == 1 + 10
    assert [c.value for c in mov[1]][:4] == ["Banca", "Data", "Valuta", "Trimestre"]


def test_cli(pdf_dir, tmp_path, capsys):
    from bankanalyst.cli import main
    out = tmp_path / "r.xlsx"
    assert main([str(pdf_dir), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "2026-Q1" in text and "Da classificare: 1" in text
    assert out.exists()
