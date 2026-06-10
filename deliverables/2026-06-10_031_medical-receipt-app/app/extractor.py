"""Receipt data extraction via OpenAI GPT-4o Vision."""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Optional

from app.schemas import ExtractionResult, LineItem

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI, APIError, APITimeoutError
    _OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    APIError = Exception  # type: ignore[assignment,misc]
    APITimeoutError = Exception  # type: ignore[assignment,misc]
    _OPENAI_AVAILABLE = False

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
  "tax_deductible": true|false|null,
  "line_items": [
    {"description": "...", "quantity": 1, "unit_price": 5.00, "total": 5.00}
  ],
  "confidence": valore tra 0 e 1 che indica la tua certezza nell'estrazione
}

Regole per tax_deductible:
- farmaci con ricetta medica: true
- farmaci da banco (OTC) con codice fiscale del paziente sul documento: true
- visite specialistiche, esami diagnostici, ticket SSN: true
- integratori alimentari, cosmetici, prodotti non medicinali: false
- prodotti parafarmaceutici non chiaramente medicinali: false
- SE NON RIESCI A DETERMINARLO CON CERTEZZA: usa null (non true).
  Il sistema chiederà all'utente di verificare manualmente.

Regola per expense_type:
- "farmaco": medicinali, farmaci, prodotti farmaceutici con AIC o obbligo di ricetta
- "visita": visita medica, consulto specialistico
- "esame": analisi del sangue, radiografie, ecografie, TAC, risonanza, ecc.
- "ticket": ticket del Servizio Sanitario Nazionale
- "dentista": cure dentistiche, ortodonzia, igiene dentale
- "altro": qualsiasi altra spesa sanitaria o parafarmaceutica
"""

_API_TIMEOUT_SEC = 30


def extract_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> ExtractionResult:
    if not _OPENAI_AVAILABLE:
        logger.warning("openai package not installed — skipping extraction")
        return ExtractionResult(confidence=0.0)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not set — skipping extraction")
        return ExtractionResult(confidence=0.0)

    client = OpenAI(api_key=api_key, timeout=_API_TIMEOUT_SEC)
    b64 = base64.b64encode(image_bytes).decode()

    try:
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
    except APITimeoutError:
        logger.error("OpenAI Vision API timed out after %ds", _API_TIMEOUT_SEC)
        raise
    except APIError as exc:
        logger.error("OpenAI API error during extraction: %s", exc)
        raise

    raw_text = response.choices[0].message.content.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse extraction JSON: %s — raw: %.200s", exc, raw_text)
        return ExtractionResult(confidence=0.0)

    line_items = None
    if data.get("line_items"):
        line_items = []
        for item in data["line_items"]:
            if not isinstance(item, dict):
                continue
            try:
                line_items.append(LineItem(**item))
            except Exception:
                pass

    raw_ded = data.get("tax_deductible")
    if isinstance(raw_ded, bool):
        tax_deductible: Optional[bool] = raw_ded
    else:
        tax_deductible = None  # null from model → unknown

    confidence = float(data.get("confidence") or 0.8)
    logger.info("Extraction confidence=%.2f provider=%s amount=%s",
                confidence, data.get("provider_name"), data.get("total_amount"))

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
        tax_deductible=tax_deductible,
        line_items=line_items,
        confidence=confidence,
    )


def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Render up to 3 PDF pages as JPEG and extract from the highest-confidence page."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not installed — cannot extract from PDF")
        return ExtractionResult(confidence=0.0)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.error("Failed to open PDF: %s", exc)
        return ExtractionResult(confidence=0.0)

    page_count = len(doc)
    pages_to_try = min(page_count, 3)
    best: ExtractionResult = ExtractionResult(confidence=0.0)

    for i in range(pages_to_try):
        try:
            page = doc[i]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("jpeg")
            result = extract_from_image(img_bytes, mime_type="image/jpeg")
            if result.confidence > best.confidence:
                best = result
        except Exception as exc:
            logger.warning("Error extracting page %d: %s", i, exc)

    doc.close()
    best.pages_extracted = page_count
    return best


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
