from pathlib import Path
from generate_invoice import generate
from send_email import send_pdf

TO = "mario.rossi@example.com"
SUBJECT = "Fattura INV-003 — Web design services"
BODY = "Gentile Mario Rossi,\n\nIn allegato la fattura INV-003 per i servizi di web design.\n\nGrazie per la collaborazione."


def run():
    print("Generating invoice PDF...")
    pdf_path = generate()
    print(f"  → {pdf_path} created")

    print(f"Sending to {TO}...")
    msg_id = send_pdf(to=TO, subject=SUBJECT, body=BODY, pdf_path=pdf_path)
    print(f"  → Sent! Gmail message ID: {msg_id}")
    print("\n✅ DONE — INV-003_Mario_Rossi.pdf delivered to mario.rossi@example.com")


if __name__ == "__main__":
    run()
