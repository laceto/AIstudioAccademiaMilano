from fpdf import FPDF
from datetime import date
from pathlib import Path

OUTPUT = Path(__file__).parent / "INV-003_Mario_Rossi.pdf"


class InvoicePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 20)
        self.cell(0, 15, "FATTURA", align="C")
        self.ln(5)


def generate(
    invoice_number: str = "INV-003",
    client_name: str = "Mario Rossi",
    service: str = "Web design services",
    amount: float = 500.00,
    output_path: Path = OUTPUT,
) -> Path:
    pdf = InvoicePDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"N. Fattura: {invoice_number}", ln=True)
    pdf.cell(0, 8, f"Data: {date.today()}", ln=True)
    pdf.ln(8)

    pdf.cell(0, 8, "Cliente:", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, client_name, ln=True)
    pdf.ln(8)

    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(130, 8, "Descrizione", border=1, fill=True)
    pdf.cell(50, 8, "Importo", border=1, fill=True, align="R", ln=True)

    pdf.set_font("Helvetica", size=11)
    pdf.cell(130, 8, service, border=1)
    pdf.cell(50, 8, f"€{amount:,.2f}", border=1, align="R", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(130, 10, "TOTALE", align="R")
    pdf.cell(50, 10, f"€{amount:,.2f}", border=1, align="R", ln=True)

    pdf.output(str(output_path))
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Invoice created: {path}")
