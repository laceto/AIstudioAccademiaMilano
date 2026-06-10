"""Receipt data extraction via OpenAI GPT-4o Vision."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from app.schemas import ExtractionResult, LineItem

_EXTRACTION_PROMPT = """
Sei un assistente specializzato nell'analisi di scontrini e ricevute mediche italiane.
Analizza il documento fornito ed estrai le informazioni nel formato JSON seguente.
Rispondi SOLO con il JSON valido, senza spiegazioni aggiuntive.

{
  "date": "YYYY-MM-DD o null",
  "receipt_number": "numero scontrino/fattura o null",
  "provider_name": "nome farmacia, studio medico, laboratorio ecc.",
  "provider_tax_id": "P.IVA o codice fiscale del fornitore o null",
  "expense_type": "farmaco|visita|esame|ticket|dentista|altro",
  "description": "descrizione sintetica del prodotto/servizio",
  "payment_method": "Contanti|Carta di credito|Carta di debito|Bancomat|Bonifico|Satispay|PayPal|Altro",
  "total_amount": numero con decimali (es. 12.50),
  "deductible_amount": importo detraibile 730 (uguale a total_amount se detraibile, 0 se non detraibile),
  "tax_deductible": true se la spesa è detraibile al 19% per il 730 italiano,
  "line_items": [
    {"description": "...", "quantity": 1, "unit_price": 5.00, "total": 5.00}
  ],
  "confidence": valore tra 0 e 1 che indica la tua certezza nell'estrazione
}

Regole per tax_deductible:
- farmaci con ricetta medica: true
- farmaci da banco (OTC) con codice fiscale sul documento: true
- visite specialistiche, esami diagnostici, ticket SSN: true
- integratori, cosmetici, prodotti non medicali: false
- se non riesci a determinarlo con certezza, usa true con confidence bassa.

Regola per expense_type:
- "farmaco": medicinali, farmaci, prodotti farmaceutici
- "visita": visita medica, consulto specialistico
- "esame": analisi del sangue, radiografie, ecografie, TAC, ecc.
- "ticket": ticket del Servizio Sanitario Nazionale
- "dentista": cure dentistiche, ortodonzia
- "altro": qualsiasi altra spesa sanitaria
"""


def extract_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> ExtractionResult:
    try:
        from openai import OpenAI
    except ImportError:
        return ExtractionResult(confidence=0.0)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ExtractionResult(confidence=0.0)

    client = OpenAI(api_key=api_key)
    b64 = base64.b64encode(image_bytes).decode()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            }
        ],
        max_tokens=1000,
        temperature=0,
    )

    raw_text = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return ExtractionResult(confidence=0.0)

    line_items = None
    if data.get("line_items"):
        line_items = [LineItem(**item) for item in data["line_items"] if isinstance(item, dict)]

    return ExtractionResult(
        date=data.get("date"),
        receipt_number=data.get("receipt_number"),
        provider_name=data.get("provider_name"),
        provider_tax_id=data.get("provider_tax_id"),
        expense_type=data.get("expense_type", "altro"),
        description=data.get("description"),
        payment_method=data.get("payment_method"),
        total_amount=_safe_float(data.get("total_amount")),
        deductible_amount=_safe_float(data.get("deductible_amount")),
        tax_deductible=bool(data.get("tax_deductible", True)),
        line_items=line_items,
        confidence=float(data.get("confidence", 0.8)),
    )


def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Convert first page of PDF to image and extract."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ExtractionResult(confidence=0.0)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("jpeg")
    doc.close()
    return extract_from_image(img_bytes, mime_type="image/jpeg")


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
