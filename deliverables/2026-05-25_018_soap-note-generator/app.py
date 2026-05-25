"""
SOAP Note Generator — Strumento AI per psicologi
AI Studio Accademia Milano — deliverable 018

DISCLAIMER: Questo strumento genera bozze di note cliniche tramite AI.
Ogni output deve essere revisionato e firmato dal clinico responsabile
prima di qualsiasi uso clinico o legale.
"""

import io
import json
import os
from datetime import date

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SOAP Note Generator",
    page_icon="🧠",
    layout="centered",
)

# ---------------------------------------------------------------------------
# API key guard — fail fast before any other import that costs money
# ---------------------------------------------------------------------------
_api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
if not _api_key:
    st.error(
        "OPENAI_API_KEY non trovata. "
        "Imposta la variabile d'ambiente oppure aggiungi la chiave in Streamlit Secrets."
    )
    st.stop()

from openai import OpenAI  # noqa: E402 — imported after key check

# ---------------------------------------------------------------------------
# OpenAI client — initialised once at module level
# ---------------------------------------------------------------------------
_client = OpenAI(api_key=_api_key)

# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
Sei un assistente clinico per psicologi. Ricevi appunti liberi di una seduta \
terapeutica e li strutturi in una nota SOAP professionale in italiano.

Regole:
- Usa un linguaggio clinico ma leggibile
- Non inventare informazioni non presenti negli appunti
- Se un'informazione manca per una sezione, scrivi "Non riportato dalla seduta"
- NON includere nomi propri del paziente — usa solo il codice paziente fornito
- Tono: professionale, neutro, clinico

Approccio terapeutico del clinico: {approach}
Numero seduta: {session_num}
"""


def generate_soap(
    notes: str,
    patient_code: str,
    session_num: str,
    approach: str,
) -> dict:
    """
    Call gpt-4o-mini and return a dict with keys:
    soggettivo, oggettivo, assessment, piano.

    Raises ValueError if the model response cannot be parsed as JSON.
    """
    system_msg = SYSTEM_PROMPT_TEMPLATE.format(
        approach=approach,
        session_num=session_num,
    )
    user_msg = (
        f"Appunti della seduta:\n\n{notes}\n\n"
        "Restituisci un JSON con le chiavi: soggettivo, oggettivo, assessment, piano"
    )

    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Risposta JSON non valida dal modello: {exc}") from exc

    required_keys = {"soggettivo", "oggettivo", "assessment", "piano"}
    missing = required_keys - data.keys()
    if missing:
        raise ValueError(f"Chiavi mancanti nella risposta: {missing}")

    return {k: str(data[k]) for k in required_keys}


def create_soap_pdf(
    soap_dict: dict,
    patient_code: str,
    approach: str,
) -> bytes:
    """
    Build a SOAP note PDF (A4) from the structured dict.
    Returns raw PDF bytes.
    """
    from fpdf import FPDF

    today = date.today().strftime("%d/%m/%Y")
    patient_label = patient_code.strip() if patient_code.strip() else "N/D"

    FOOTER_TEXT = (
        "BOZZA — Documento generato da AI. "
        "Revisione clinica obbligatoria prima dell'uso."
    )

    class _SoapPDF(FPDF):
        def footer(self_):
            self_.set_y(-15)
            self_.set_font("Helvetica", "I", 8)
            self_.set_text_color(180, 0, 0)
            self_.cell(0, 10, FOOTER_TEXT, align="C")
            self_.set_text_color(0, 0, 0)

    pdf = _SoapPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ------------------------------------------------------------------
    # Header block
    # ------------------------------------------------------------------
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "NOTA SOAP — BOZZA AI", ln=False, align="L")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, today, ln=True, align="R")

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Codice paziente: {patient_label}", ln=True)
    if approach and approach != "Non specificato":
        pdf.cell(0, 7, f"Approccio: {approach}", ln=True)

    # Horizontal rule
    pdf.set_draw_color(100, 100, 100)
    pdf.set_line_width(0.5)
    pdf.line(pdf.get_x(), pdf.get_y() + 2, pdf.get_x() + 190, pdf.get_y() + 2)
    pdf.ln(6)

    # ------------------------------------------------------------------
    # SOAP sections
    # ------------------------------------------------------------------
    sections = [
        ("S — SOGGETTIVO", soap_dict.get("soggettivo", "")),
        ("O — OGGETTIVO", soap_dict.get("oggettivo", "")),
        ("A — ASSESSMENT / VALUTAZIONE", soap_dict.get("assessment", "")),
        ("P — PIANO", soap_dict.get("piano", "")),
    ]

    for label, body in sections:
        # Section heading
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 8, label, ln=True, fill=True)
        pdf.ln(1)

        # Body text — wrapped
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, body)
        pdf.ln(5)

    # ------------------------------------------------------------------
    # Signature area
    # ------------------------------------------------------------------
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Firma del clinico responsabile: ____________________________", ln=True)
    pdf.cell(0, 7, f"Data: ________________    Timbro: ________________", ln=True)

    result = pdf.output()
    return bytes(result) if not isinstance(result, bytes) else result


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "soap_dict" not in st.session_state:
    st.session_state["soap_dict"] = None
if "pdf_bytes" not in st.session_state:
    st.session_state["pdf_bytes"] = None

# ---------------------------------------------------------------------------
# Always-visible disclaimer
# ---------------------------------------------------------------------------
st.markdown(
    "<p style='color:red; font-weight:bold;'>"
    "&#9888;&#65039; Questa e&#768; una bozza generata da AI. "
    "Deve essere revisionata e firmata dal clinico responsabile "
    "prima di qualsiasi uso clinico o legale."
    "</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------
st.title("Generatore Note SOAP")
st.caption(
    "Strumento AI per psicologi — bozza da revisionare prima dell’uso clinico"
)

session_notes = st.text_area(
    "Note libere della seduta",
    height=250,
    placeholder=(
        "Scrivi qui le tue osservazioni sulla seduta, "
        "cosa ha detto il paziente, come ti è sembrato, cosa hai pianificato..."
    ),
    key="session_notes",
)

with st.expander("Dati facoltativi"):
    patient_code = st.text_input("Codice paziente (opzionale)")
    session_num = st.selectbox(
        "Numero seduta",
        ["Prima seduta", "Seduta 2-5", "Seduta 6-10", "Oltre 10 sedute"],
    )
    approach = st.selectbox(
        "Approccio terapeutico",
        [
            "Non specificato",
            "Cognitivo-comportamentale (CBT)",
            "Psicodinamico",
            "Sistemico-relazionale",
            "ACT",
            "EMDR",
            "Umanistico",
        ],
    )

generate_btn = st.button("Genera nota SOAP 🧠")

if generate_btn:
    if not session_notes.strip():
        st.warning("Inserisci le note della seduta prima di generare la nota SOAP.")
    else:
        with st.spinner("Analisi in corso…"):
            try:
                soap = generate_soap(
                    notes=session_notes,
                    patient_code=patient_code,
                    session_num=session_num,
                    approach=approach,
                )
                pdf_bytes = create_soap_pdf(
                    soap_dict=soap,
                    patient_code=patient_code,
                    approach=approach,
                )
                st.session_state["soap_dict"] = soap
                st.session_state["pdf_bytes"] = pdf_bytes
            except ValueError as exc:
                st.error(f"Errore nella generazione. Riprova. ({exc})")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Errore imprevisto: {exc}")

# ---------------------------------------------------------------------------
# Results display — survives reruns via session_state
# ---------------------------------------------------------------------------
soap_result: dict | None = st.session_state.get("soap_dict")
pdf_result: bytes | None = st.session_state.get("pdf_bytes")

if soap_result:
    st.divider()
    st.subheader("Nota SOAP generata")

    section_labels = {
        "soggettivo": "S — Soggettivo",
        "oggettivo": "O — Oggettivo",
        "assessment": "A — Assessment / Valutazione",
        "piano": "P — Piano",
    }
    for key, label in section_labels.items():
        with st.expander(label, expanded=True):
            st.write(soap_result.get(key, ""))

    if pdf_result:
        st.download_button(
            label="Scarica PDF",
            data=pdf_result,
            file_name=f"soap_note_{date.today().isoformat()}.pdf",
            mime="application/pdf",
        )

# ---------------------------------------------------------------------------
# Footer disclaimer (repeated at bottom)
# ---------------------------------------------------------------------------
st.divider()
st.markdown(
    "<p style='color:red; font-size:0.85em;'>"
    "&#9888;&#65039; Questa e&#768; una bozza generata da AI. "
    "Deve essere revisionata e firmata dal clinico responsabile "
    "prima di qualsiasi uso clinico o legale."
    "</p>",
    unsafe_allow_html=True,
)
