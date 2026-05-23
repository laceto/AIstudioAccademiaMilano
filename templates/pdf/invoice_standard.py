from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InvoiceTemplate:
    invoice_number: str
    client_name: str
    amount: float
    service: str
    date: str
    currency: str = "EUR"

    def __post_init__(self):
        if not self.client_name:
            raise ValueError("client_name is required")
        if self.amount is None:
            raise ValueError("amount is required")

    def is_valid(self) -> bool:
        return bool(
            self.invoice_number
            and self.client_name
            and self.amount is not None
            and self.service
            and self.date
        )

    def render(self) -> bytes:
        from fpdf import FPDF

        class _InvoicePDF(FPDF):
            def header(self_):
                self_.set_font("Helvetica", "B", 18)
                self_.cell(0, 12, "FATTURA", align="C")
                self_.ln(4)

        pdf = _InvoicePDF()
        pdf.compress = False  # keep text readable in raw bytes for tests
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"N. Fattura: {self.invoice_number}", ln=True)
        pdf.cell(0, 7, f"Data: {self.date}", ln=True)
        pdf.ln(6)

        pdf.cell(0, 7, "Cliente:", ln=True)
        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 7, self.client_name, ln=True)
        pdf.ln(6)

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(130, 8, "Descrizione", border=1, fill=True)
        pdf.cell(50, 8, "Importo", border=1, fill=True, align="R", ln=True)

        pdf.set_font("Helvetica", size=11)
        pdf.cell(130, 8, self.service, border=1)
        pdf.cell(50, 8, f"{self.currency} {self.amount:,.2f}", border=1, align="R", ln=True)

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(130, 10, "TOTALE", align="R")
        pdf.cell(50, 10, f"{self.currency} {self.amount:,.2f}", border=1, align="R", ln=True)

        result = pdf.output()
        return bytes(result) if not isinstance(result, bytes) else result
