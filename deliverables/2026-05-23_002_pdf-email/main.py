from pathlib import Path
from generate_pdf import generate
from send_email import send_pdf

TO = "stekkino@hotmail.it"
SUBJECT = "funziona"
BODY = "In allegato il tuo PDF."


def run():
    print("Generating PDF...")
    pdf_path = generate()
    print(f"  → {pdf_path} created")

    print(f"Sending to {TO}...")
    msg_id = send_pdf(to=TO, subject=SUBJECT, body=BODY, pdf_path=pdf_path)
    print(f"  → Sent! Gmail message ID: {msg_id}")
    print("\n✅ DONE — funziona.pdf delivered to stekkino@hotmail.it")


if __name__ == "__main__":
    run()
