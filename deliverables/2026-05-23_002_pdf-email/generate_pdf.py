from fpdf import FPDF
from pathlib import Path

OUTPUT = Path(__file__).parent / "funziona.pdf"


def generate(output_path: Path = OUTPUT) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", size=48)
    pdf.set_y(120)
    pdf.cell(0, 20, "funziona", align="C")
    pdf.output(str(output_path))
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"PDF created: {path}")
