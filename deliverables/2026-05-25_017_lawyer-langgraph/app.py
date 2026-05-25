"""
Avvocato AI — LangGraph Streamlit UI.
Run: streamlit run app.py
Requires ANTHROPIC_API_KEY in environment or .streamlit/secrets.toml.
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state import BILLING_RATES, CONTACT_METHODS, DISCLAIMER_IT, MATTER_TYPES

st.set_page_config(
    page_title="Avvocato AI — LangGraph",
    page_icon="⚖️",
    layout="wide",
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚖️ Avvocato AI")
st.caption(
    "Studio Legale intelligente — Intake · Ricerca · Redazione · QA · Fatturazione · Consegna"
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Pipeline")
    st.code(
        "START\n"
        "  └─► [Intake] classifica materia\n"
        "        └─► [Ricercatore] normativa IT/EU\n"
        "              └─► [Redattore] bozza documento\n"
        "                    ├─► [LegalQA] ──────┐ parallel\n"
        "                    └─► [Compliance] ───┘\n"
        "                    └─► [QA Merge]\n"
        "                          └─► [Fatturazione]\n"
        "                                └─► [Consegna]\n"
        "                                      └─► END",
        language=None,
    )

    st.divider()
    st.subheader("Tariffe (ref. D.M. 55/2014)")
    for k, v in BILLING_RATES.items():
        label = MATTER_TYPES.get(k, k)
        st.markdown(f"- **{label}**: €{v['hourly']}/h (min {v['min_hours']}h)")

    st.divider()
    st.subheader("Canali di consegna")
    for m in CONTACT_METHODS:
        icon = {"email": "📧", "discord": "🎮", "whatsapp": "📱", "portale_sicuro": "🔒"}.get(m, "📤")
        st.markdown(f"{icon} `{m}`")
    st.info("🎮 **Discord** — ideale per clienti che giocano su PS5/Xbox: ricevono la risposta dell'avvocato direttamente nel gioco (via Discord overlay).")

# ── Main form ─────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Nuova Richiesta")

    client_name    = st.text_input("Nome cliente", value="Michele")
    contact_method = st.selectbox("Canale di risposta", CONTACT_METHODS,
                                   format_func=lambda m: {
                                       "email": "📧 Email",
                                       "discord": "🎮 Discord (gaming)",
                                       "whatsapp": "📱 WhatsApp",
                                       "portale_sicuro": "🔒 Portale Sicuro",
                                   }.get(m, m))
    request = st.text_area(
        "Descrivi il tuo caso",
        placeholder=(
            "Es. Ho ricevuto un avviso di accertamento dall'Agenzia delle Entrate "
            "per euro 15.000 di IVA non versata nel 2022. Come posso difendermi?"
        ),
        height=150,
    )

    st.markdown("**Casi di esempio:**")
    e1, e2, e3 = st.columns(3)
    with e1:
        if st.button("💼 Contratto"):
            request = "Devo rescindere un contratto di locazione commerciale prima della scadenza. L'inquilino non paga da 3 mesi. Cosa devo fare?"
    with e2:
        if st.button("👨‍👩‍👧 Famiglia"):
            request = "Sto per separarmi e ho due figli. Vorrei capire come funziona l'affidamento condiviso e l'assegno di mantenimento."
    with e3:
        if st.button("🏢 Societario"):
            request = "Voglio aprire una SRL con un socio. Quali clausole essenziali deve avere lo statuto per proteggermi in caso di conflitti futuri?"

    provider = st.selectbox("Provider LLM", ["anthropic", "openai"],
                             format_func=lambda p: {"anthropic": "🟣 Anthropic (Haiku + Sonnet)", "openai": "🟢 OpenAI (gpt-4o-mini + gpt-4o)"}[p])
    if provider == "anthropic":
        api_key = st.text_input("Anthropic API Key", type="password",
                                 value=os.environ.get("ANTHROPIC_API_KEY", ""))
    else:
        api_key = st.text_input("OpenAI API Key", type="password",
                                 value=os.environ.get("OPENAI_API_KEY", ""))

    run_btn = st.button("⚖️ Avvia Pratica", type="primary",
                         disabled=not (request and api_key))

with col_right:
    st.subheader("Registro Procedimento")
    trace_placeholder = st.empty()

# ── Agent icons ───────────────────────────────────────────────────────────────
ICONS = {
    "Intake":       "📋",
    "Ricercatore":  "🔍",
    "Redattore":    "✍️",
    "LegalQA":      "⚖️",
    "Compliance":   "📜",
    "QA Merge":     "🔀",
    "Fatturazione": "💶",
    "Consegna":     "📤",
}


def parse_step(content: str) -> tuple[str, str]:
    if content.startswith("[") and "]" in content:
        agent = content[1:content.index("]")]
        body  = content[content.index("]") + 1:].strip().lstrip("—").strip()
        return agent, body
    return "Agent", content


# ── Run ───────────────────────────────────────────────────────────────────────
if run_btn and request and api_key:
    if provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
    else:
        os.environ["OPENAI_API_KEY"] = api_key

    from graph import run_case

    graph_config = {"configurable": {"provider": provider}}
    steps: list[dict] = []
    final_state = None

    with st.spinner("Elaborazione pratica in corso…"):
        try:
            steps, final_state = run_case(request, client_name, contact_method, config=graph_config)
        except Exception as exc:
            st.error(f"Errore pipeline: {exc}")
            st.exception(exc)

    # Render trace
    with trace_placeholder.container():
        for step in steps:
            agent, body = parse_step(step["content"])
            icon = ICONS.get(agent, "🤖")
            st.markdown(f"{icon} **{agent}** — {body}")

    # ── Results ────────────────────────────────────────────────────────────
    if final_state:
        st.divider()

        tab_doc, tab_inv, tab_qa, tab_raw = st.tabs([
            "📄 Documento", "💶 Fattura", "✅ QA", "🔧 Raw State"
        ])

        with tab_doc:
            draft = final_state.get("draft_document", "")
            if draft:
                st.markdown(draft)
            else:
                st.info("Documento non disponibile.")

        with tab_inv:
            inv = final_state.get("invoice")
            if inv:
                c1, c2, c3 = st.columns(3)
                c1.metric("Onorario base", f"€{inv.get('onorario_base_eur', 0):.2f}")
                c2.metric("IVA 22%",       f"€{inv.get('iva_22_eur', 0):.2f}")
                c3.metric("Totale",        f"€{inv.get('totale_eur', 0):.2f}")
                st.json(inv)

        with tab_qa:
            if final_state.get("qa_passed"):
                st.success("QA superato — documento pronto per la consegna.")
            else:
                st.error(f"QA fallito: {final_state.get('qa_issues')}")
            for r in final_state.get("review_reports", []):
                with st.expander(r.get("reviewer", "reviewer")):
                    st.json(r)

        with tab_raw:
            # Show full state (excluding messages for brevity)
            safe = {k: v for k, v in final_state.items() if k not in ("messages", "draft_document")}
            st.json(safe)

        dr = final_state.get("delivery_result")
        if dr:
            icon_map = {"email": "📧", "discord": "🎮", "whatsapp": "📱", "portale_sicuro": "🔒"}
            icon = icon_map.get(dr.get("channel", ""), "📤")
            st.success(f"{icon} Consegnato via **{dr.get('channel')}** — {dr.get('note')}")
