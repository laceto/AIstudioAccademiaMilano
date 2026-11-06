"""Offline tests for bankanalyst (delivery 045): synthetic Credem and ING statements built with fpdf2."""
import os
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


def make_credem_real(path, stripes=False):
    """Layout of the real Credem statements: summary page, then a table where each movement is a block
    (description above and below the row holding dates and amount), then a 'conto scalare' to ignore.
    With stripes, every other movement has a shaded background and one description has a blank line
    in it, as on the real pages: only the stripes tell where that movement ends."""
    pdf = fpdf.FPDF(unit="pt", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_font("Helvetica", size=8)

    def at(x, y, text, w=0, align="L"):
        pdf.set_xy(x, y)
        pdf.cell(w, 6, text, align=align)

    pdf.add_page()
    at(220, 40, "Estratto conto")
    at(40, 100, "DATA")
    at(40, 110, "04/04/2026")
    at(40, 200, "SALDO PRECEDENTE")
    at(380, 200, "1.000,00")
    at(40, 212, "SALDO FINE PERIODO")
    at(380, 212, "3.918,55")
    at(40, 240, "Legenda")
    at(40, 250, "Entrate Uscite")
    at(40, 780, "CREDITO EMILIANO SPA, Capogruppo del Gruppo Bancario Credito Emiliano - Credem")

    pdf.add_page()
    at(40, 40, "segue - Estratto conto al 31 marzo 2026")
    at(40, 60, "Elenco movimenti")
    pdf.set_font("Helvetica", size=6)
    for x, word in [(40, "DATA CONTABILE"), (93, "DATA VALUTA"), (147, "DESCRIZIONE OPERAZIONE"),
                    (398, "IMPORTO A DEBITO"), (478, "IMPORTO A CREDITO")]:
        at(x, 76, word)
    pdf.set_font("Helvetica", size=8)

    def money(y, amount, credit=False):
        at(477 if credit else 397, y, amount, w=78, align="R")

    at(147, 88, "SALDO PRECEDENTE")
    money(88, "1.000,00", credit=True)
    y = 106
    blocks = [
        (["PAGOBANCOMAT 30/12/25,ORE 19:13,TESS.000000001"], "02/01/2026", "30/12/2025", "", "21,96", False,
         ["caseificio esempio"]),
        ([], "10/01/2026", "10/01/2026", "CARTA EGO", "26,99", False, []),
        (["BONIFICO A CREDITO", "", "inps"] if stripes else ["BONIFICO A CREDITO", "inps"],
         "21/02/2026", "21/02/2026", "", "57,50", True, ["rif. 123"]),
        (["EMOLUMENTI ACME Italia SpA"], "28/01/2026", "28/01/2026", "stipendio 01-2026",
         "3.010,00", True, ["rif. 0000000000000001"]),
        (["PRELIEVO BANCOMAT"], "12/02/2026", "11/02/2026", "", "100,00", False,
         ["11/02/26,ore 12:36,tess.000000001 unicredit s.p.a."]),
    ]
    for n, (above, booking, value, inline, amount, credit, below) in enumerate(blocks):
        if stripes and n % 2 == 0:
            pdf.set_fill_color(229, 236, 232)
            pdf.rect(38, y - 4, 54, 5.2 * (len(above) + 1 + len(below)) + 6, style="F")
        for text in above:
            at(147, y, text)
            y += 5.2
        at(40, y, booking)
        at(93, y, value)
        if inline:
            at(147, y, inline)
        money(y, amount, credit)
        y += 5.2
        for text in below:
            at(147, y, text)
            y += 5.2
        y += 8
    at(147, y, "SALDO FINE PERIODO")
    money(y, "3.918,55", credit=True)

    pdf.add_page()
    at(40, 40, "Conto Scalare")
    at(40, 60, "DATA VALUTA SALDI PER VALUTA GIORNI NUMERI DEBITORI NUMERI CREDITORI")
    at(40, 72, "22/01/2026 1.958,17 1 1.958,17")
    pdf.output(str(path))
    return path


@pytest.mark.parametrize("stripes", [False, True])
def test_parse_credem_real_layout(tmp_path, stripes):
    st = parse_statement(make_credem_real(tmp_path / "Estratto_Conto_con_Allungo_31mar2026.pdf", stripes))
    assert st.bank == "credem"
    assert [t.amount for t in st.transactions] == [
        Decimal("-21.96"), Decimal("-26.99"), Decimal("57.50"), Decimal("3010.00"), Decimal("-100.00")]
    d = [t.description for t in st.transactions]
    assert d[0] == "PAGOBANCOMAT 30/12/25,ORE 19:13,TESS.000000001 caseificio esempio"
    assert d[1] == "CARTA EGO"
    assert d[2] == "BONIFICO A CREDITO inps rif. 123"
    assert d[3].startswith("EMOLUMENTI") and "stipendio 01-2026" in d[3] and d[3].endswith("0000000000000001")
    assert d[4].startswith("PRELIEVO BANCOMAT 11/02/26")
    assert st.transactions[0].value_date == date(2025, 12, 30)
    assert st.opening == Decimal("1000.00") and st.closing == Decimal("3918.55")
    assert st.reconciliation() == "ok"
    assert st.warnings == []


DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_ing_real(path, currency="EUR"):
    """Layout of the real ING (Conto Corrente Arancio) statements: header over three lines, amount followed
    by a separate '€', description starting on the amount row and continuing below, some continuation
    lines starting with a date, opening and closing balance as dated rows, then a conto scalare."""
    pdf = fpdf.FPDF(unit="pt", format="A4")
    pdf.set_auto_page_break(False)
    if currency == "€":  # the core fonts are latin-1 only
        pdf.add_font("DejaVu", fname=DEJAVU)
        pdf.set_font("DejaVu", size=7)
    else:
        pdf.set_font("Helvetica", size=7)

    def at(x, y, text, w=0, align="L"):
        pdf.set_xy(x, y)
        pdf.cell(w, 6, text, align=align)

    pdf.add_page()
    at(56, 40, "ESTRATTO CONTO CONTO CORRENTE ARANCIO")
    at(56, 52, "Estratto conto Trimestrale al 31/12/2026")
    at(56, 74, "DATA")
    for x, word in [(124, "DATA VALUTA"), (199, "USCITE"), (268, "ENTRATE"), (337, "DESCRIZIONE")]:
        at(x, 80, word)
    at(56, 86, "OPERAZIONE")

    def row(y, booking, value, amount, credit, desc):
        at(63, y, booking)
        if value:
            at(134, y, value)
        pdf.set_xy(200 if not credit else 262, y)
        pdf.cell(47, 6, amount, align="R")
        at(249 if not credit else 311, y, currency)  # "EUR" is wider than "€": keep it clear of the description
        at(334, y, desc)

    y = 105
    row(y, "30/09/2026", None, "647,67", True, "SALDO INIZIALE")
    y += 22.3
    blocks = [
        ("01/10/2026", "28/09/2026", "87,11", False, "PAGAMENTO CARTA - OPERAZIONE MASTERCARD DEL",
         ["28/09/2026 ALLE ORE 11:19 CON CARTA", "XXXXXXXXXXXX0000 DIV=EUR IMPORTO IN DIVISA=87.11 /",
          "IMPORTO IN EURO=87.11 PRESSO ESSELUNGA -", "TRANSAZIONE C-LESS"]),
        ("03/10/2026", "03/10/2026", "1.100,00", True, "ACCREDITO BONIFICO - BONIFICO N. 1",
         ["ORDINANTE MARIO ROSSI NOTE: SPESE FAMILIARI"]),
        ("05/10/2026", "05/10/2026", "2,00", False, "COMMISSIONE", []),
    ]
    for booking, value, amount, credit, desc, below in blocks:
        row(y, booking, value, amount, credit, desc)
        for text in below:
            y += 10.2
            at(334, y, text)
        y += 22.3
    row(y, "31/12/2026", None, "1.658,56", True, "SALDO FINALE")

    pdf.add_page()
    at(56, 60, "DATA SALDI IMPORTI PER N° GG NUMERI TASSO INTERESSI NUMERI TASSO")
    at(56, 80, "01/10/2026 647,67 647,67 1 0,00 0,0000 647,67")
    pdf.output(str(path))
    return path


@pytest.mark.parametrize("currency", ["EUR", "€"])
def test_parse_ing_real_layout(tmp_path, currency):
    if currency == "€" and not os.path.exists(DEJAVU):
        pytest.skip("DejaVu font not installed")
    st = parse_statement(make_ing_real(tmp_path / "5_0000000000_000000_100.pdf", currency))
    assert st.bank == "ing"
    assert [t.amount for t in st.transactions] == [Decimal("-87.11"), Decimal("1100.00"), Decimal("-2.00")]
    d = [t.description for t in st.transactions]
    assert d[0] == ("PAGAMENTO CARTA - OPERAZIONE MASTERCARD DEL 28/09/2026 ALLE ORE 11:19 CON CARTA "
                    "XXXXXXXXXXXX0000 DIV=EUR IMPORTO IN DIVISA=87.11 / IMPORTO IN EURO=87.11 PRESSO ESSELUNGA - "
                    "TRANSAZIONE C-LESS")
    assert d[1] == "ACCREDITO BONIFICO - BONIFICO N. 1 ORDINANTE MARIO ROSSI NOTE: SPESE FAMILIARI"
    assert d[2] == "COMMISSIONE"
    assert st.opening == Decimal("647.67") and st.closing == Decimal("1658.56")
    assert st.reconciliation() == "ok"
    assert st.warnings == []


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


def test_personal_rules_layer_on_defaults(tmp_path):
    rules = tmp_path / "mie_regole.yaml"
    rules.write_text("overrides:\n  'asilo esempio': Famiglia e istruzione\n"
                     "categories:\n  - name: Giroconti tra conti\n    patterns: ['a favore di mario rossi giro']\n",
                     encoding="utf-8")
    loaded = load_rules(rules)
    c = Classifier(loaded)
    assert c.classify(_tx("BONIFICO A DEBITO a favore di mario rossi giro gennaio", "-1500")) == "Giroconti tra conti"
    assert "Giroconti tra conti" in loaded.transfers
    assert c.classify(_tx("BONIFICO A DEBITO a favore di asilo esempio srl", "-677")) == "Famiglia e istruzione"
    assert c.classify(_tx("PAGAMENTO MAESTRO ESSELUNGA -ITA", "-70")) == "Spesa alimentare"  # defaults still apply


@pytest.mark.parametrize("desc,amount,expected", [
    # Seen on real Credem statements: each was misfiled by an earlier version of the rules.
    ("BONIFICO A CREDITO universita' di esempio cup h00x00000000000 compenso", "589.86", "Stipendio e redditi"),
    ("BONIFICO A CREDITO inps assegno unico per 1 figli/o", "57.50", "Assegni e contributi pubblici"),
    ("COMM. BONIFICO ISTANTANEO", "-0.58", "Commissioni e costi bancari"),
    ("BOLLI C/C E DEPOSITI A RISPARMIO", "-8.55", "Commissioni e costi bancari"),
    ("RICARICA-RIMBORSO CANONE", "5", "Commissioni e costi bancari"),
    ("CARTA EGO", "-26.99", "Carta di credito (addebito mensile)"),
    ("BONIFICO A DEBITO a favore di studio notarile atto compravendita", "-2622.61", "Casa: acquisto, lavori, notaio"),
    ("BONIFICO A DEBITO a favore di lara rossi rca megane 25/26", "-385", "Assicurazioni"),
    ("PAGOBANCOMAT 04/11/24,ORE 09:08,TESS.000000001 tabaccheria di rossi", "-5.5", "Tabacchi"),
    # ING card payments: the merchant follows PRESSO in a long description.
    ("PAGAMENTO CARTA - OPERAZIONE MASTERCARD DEL 01/02/2025 IMPORTO IN EURO=59.14 PRESSO DISTRIBUTORE AREA SERV",
     "-59.14", "Trasporti e auto"),
    ("PAGAMENTO CARTA - OPERAZIONE MASTERCARD PRESSO BERTAME KITCHEN GARAGE - TRANSAZIONE C-LESS", "-107",
     "Ristoranti e bar"),
    ("CEDOLE/DIVIDENDI/PREMI ESTR. - INCASSO CEDOLA DEL TITOLO BTP", "17.5", "Rendite finanziarie"),
    ("IMPOSTA DI BOLLO TRADING - IMPOSTA DI BOLLO TOL DOSSIER LUG-SET 2024", "-1", "Commissioni e costi bancari"),
])
def test_default_rules_on_real_descriptions(desc, amount, expected):
    assert Classifier(load_rules()).classify(_tx(desc, amount)) == expected


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
