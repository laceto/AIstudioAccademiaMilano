"""
Psy-Assist - AI assistant for psychologists.
3 tabs: SOAP notes, therapeutic homework, psychoeducation sheets.
Requires: ANTHROPIC_API_KEY in .env or Streamlit secrets.
Model: claude-haiku-4-5-20251001
"""

from __future__ import annotations
import os
from pathlib import Path
import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", "")
_MODEL = "claude-haiku-4-5-20251001"

DISCLAIMER = (
    "**Nota professionale:** questo strumento supporta la documentazione clinica "
    "e non sostituisce il giudizio professionale del clinico."
)


def _client() -> anthropic.Anthropic:
    if not _API_KEY:
        st.error("ANTHROPIC_API_KEY non trovata. Aggiungila in .env o nei Streamlit Secrets.")
        st.stop()
    return anthropic.Anthropic(api_key=_API_KEY)


def _call(system: str, user: str, max_tokens: int = 1024) -> str:
    client = _client()
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


# ---------------------------------------------------------------------------
# Tab 1 - Note Sessione (SOAP)
# ---------------------------------------------------------------------------

_SOAP_SYSTEM = (
    "Sei un assistente clinico per psicologi italiani.\n"
    "Ricevi un riassunto libero di una sessione terapeutica e lo trasformi in una nota\n"
    "strutturata formato SOAP (Soggettivo, Obiettivo, Valutazione, Piano).\n\n"
    "Regole:\n"
    "- Usa la terza persona per il paziente (Il paziente riferisce...)\n"
    "- Mantieni linguaggio clinico ma leggibile\n"
    "- Non aggiungere diagnosi che non siano gia presenti nel riassunto\n"
    "- Ogni sezione: 2-5 frasi concise\n"
    "- Lingua: italiano professionale\n"
)


def tab_soap() -> None:
    st.subheader("Note Sessione (SOAP)")
    st.info(DISCLAIMER)

    col1, col2 = st.columns(2)
    with col1:
        patient_code = st.text_input("Codice paziente", placeholder="es. PAZ-042")
    with col2:
        session_n = st.text_input("Numero sessione", placeholder="es. 7")

    summary = st.text_area(
        "Riassunto libero della sessione",
        height=200,
        placeholder="es. Il paziente ha descritto una settimana difficile al lavoro...",
    )

    if st.button("Genera Nota SOAP", type="primary", disabled=not summary.strip()):
        with st.spinner("Elaborazione in corso..."):
            prompt = (
                f"Codice paziente: {patient_code or 'N/D'}\n"
                f"Sessione n. {session_n or 'N/D'}\n\n"
                f"Riassunto della sessione:\n{summary}\n\n"
                "Genera la nota SOAP completa."
            )
            result = _call(_SOAP_SYSTEM, prompt, max_tokens=800)
        st.success("Nota generata")
        st.markdown("---")
        st.markdown(result)
        st.download_button(
            "Scarica nota (.txt)",
            data=result,
            file_name=f"soap_{patient_code or 'paz'}_{session_n or 'sess'}.txt",
            mime="text/plain",
        )


# ---------------------------------------------------------------------------
# Tab 2 - Compiti Terapeutici
# ---------------------------------------------------------------------------

_HOMEWORK_SYSTEM = (
    "Sei uno psicologo clinico esperto in CBT, ACT e mindfulness.\n"
    "Crea esercizi di compiti terapeutici personalizzati per il paziente descritto.\n\n"
    "Regole:\n"
    "- Massimo 3 esercizi per sessione\n"
    "- Ogni esercizio: titolo, obiettivo clinico, istruzioni step-by-step in linguaggio semplice\n"
    "- Il paziente legge direttamente: usa 'tu' e tono caldo\n"
    "- Includi la frequenza consigliata (es. ogni mattina per 5 minuti)\n"
    "- Adatta al tema e al livello del paziente\n"
    "- Lingua: italiano chiaro\n"
)

_ORIENTAMENTI = [
    "CBT (Cognitivo-Comportamentale)",
    "ACT (Acceptance & Commitment Therapy)",
    "Mindfulness-based",
    "Psicodinamica",
    "Misto / Integrativo",
]


def tab_homework() -> None:
    st.subheader("Compiti Terapeutici")
    st.info(DISCLAIMER)

    col1, col2 = st.columns(2)
    with col1:
        tema = st.text_input("Tema della sessione", placeholder="es. gestione ansia, autostima...")
    with col2:
        orientamento = st.selectbox("Approccio terapeutico", _ORIENTAMENTI)

    livello = st.select_slider(
        "Livello del paziente",
        options=["Inizio percorso", "Intermedio", "Avanzato"],
        value="Intermedio",
    )

    note = st.text_area(
        "Note sul paziente (facoltativo)",
        height=100,
        placeholder="es. preferisce esercizi pratici, difficolta con compiti scritti...",
    )

    if st.button("Genera Compiti", type="primary", disabled=not tema.strip()):
        with st.spinner("Creo gli esercizi..."):
            user_prompt = (
                f"Tema sessione: {tema}\n"
                f"Approccio: {orientamento}\n"
                f"Livello paziente: {livello}\n"
                f"Note: {note or 'nessuna'}\n\n"
                "Crea 3 esercizi terapeutici personalizzati."
            )
            result = _call(_HOMEWORK_SYSTEM, user_prompt, max_tokens=900)
        st.success("Esercizi generati")
        st.markdown("---")
        st.markdown(result)
        st.download_button(
            "Scarica esercizi (.txt)",
            data=result,
            file_name=f"compiti_{tema[:30].replace(' ', '_')}.txt",
            mime="text/plain",
        )


# ---------------------------------------------------------------------------
# Tab 3 - Psicoeducazione
# ---------------------------------------------------------------------------

_PSY_EDU_SYSTEM = (
    "Sei uno psicologo che crea materiale psicoeducativo per i pazienti.\n"
    "Scrivi una scheda informativa chiara, empatica e scientificamente accurata.\n\n"
    "Struttura obbligatoria:\n"
    "1. Cos e (definizione semplice)\n"
    "2. Come si manifesta (sintomi / segnali comuni)\n"
    "3. Perche succede (spiegazione breve, de-stigmatizzante)\n"
    "4. Cosa puoi fare (3-5 strategie pratiche)\n"
    "5. Quando chiedere aiuto\n\n"
    "Regole:\n"
    "- Linguaggio accessibile, no gergo clinico\n"
    "- Tono caldo, non allarmistico\n"
    "- Circa 400-500 parole\n"
    "- Lingua: italiano\n"
)

_ARGOMENTI = [
    "Ansia generalizzata",
    "Attacchi di panico",
    "Depressione",
    "Insonnia",
    "Bassa autostima",
    "Gestione della rabbia",
    "Stress lavorativo / burnout",
    "Lutto e perdita",
    "Relazioni disfunzionali",
    "Procrastinazione",
    "Altro (libero)",
]


def tab_psyedu() -> None:
    st.subheader("Schede Psicoeducative")
    st.info(DISCLAIMER)

    argomento_sel = st.selectbox("Argomento", _ARGOMENTI)
    argomento_libero = ""
    if argomento_sel == "Altro (libero)":
        argomento_libero = st.text_input("Specifica l argomento")

    argomento = argomento_libero if argomento_sel == "Altro (libero)" else argomento_sel

    target = st.radio(
        "Target",
        ["Adulti (generico)", "Adolescenti", "Genitori / familiari"],
        horizontal=True,
    )

    if st.button("Genera Scheda", type="primary", disabled=not argomento.strip()):
        with st.spinner("Scrivo la scheda..."):
            user_prompt = (
                f"Argomento: {argomento}\n"
                f"Target: {target}\n\n"
                "Scrivi la scheda psicoeducativa completa."
            )
            result = _call(_PSY_EDU_SYSTEM, user_prompt, max_tokens=700)
        st.success("Scheda generata")
        st.markdown("---")
        st.markdown(result)
        st.download_button(
            "Scarica scheda (.txt)",
            data=result,
            file_name=f"psy_edu_{argomento[:30].replace(' ', '_')}.txt",
            mime="text/plain",
        )


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Psy-Assist",
        page_icon="🧠",
        layout="centered",
    )
    st.title("🧠 Psy-Assist")
    st.caption("Assistente AI per psicologi — documentazione e contenuti clinici in italiano")
    st.write("")

    tab1, tab2, tab3 = st.tabs([
        "📝 Note Sessione",
        "📚 Compiti Terapeutici",
        "📄 Psicoeducazione",
    ])
    with tab1:
        tab_soap()
    with tab2:
        tab_homework()
    with tab3:
        tab_psyedu()

    st.divider()
    st.caption(
        "Psy-Assist · AI Studio Accademia Milano · "
        "Strumento di supporto professionale — non sostituisce la valutazione clinica."
    )


if __name__ == "__main__":
    main()
