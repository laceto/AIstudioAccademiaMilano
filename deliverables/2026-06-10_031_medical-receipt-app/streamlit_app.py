"""Medical Receipt Vault — mobile-optimised Streamlit UI."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from app.crud import (
    available_years,
    create_receipt,
    delete_receipt,
    get_dashboard,
    get_receipt,
    list_receipts,
    update_receipt,
)
from app.database import SessionLocal, init_db
from app.export import to_excel, to_pdf_summary
from app.extractor import extract_from_image, extract_from_pdf
from app.schemas import (
    EXPENSE_TYPES,
    PAYMENT_METHODS,
    ReceiptCreate,
    ReceiptUpdate,
)
from app.storage import get_mime_type, load_file, save_file

init_db()

st.set_page_config(
    page_title="Ricevute Sanitarie",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container { padding: 1rem 1rem 3rem; max-width: 720px; }
  .metric-card { background: #f8f9fa; border-radius: 12px; padding: 16px; margin: 8px 0; }
  .receipt-row { border-bottom: 1px solid #e9ecef; padding: 8px 0; }
  div[data-testid="stTabs"] button { font-size: 0.9rem; }
  .stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)


def db():
    return SessionLocal()


# ─── helpers ─────────────────────────────────────────────────────────────────

def _current_year() -> int:
    return datetime.now().year


def _format_euro(value) -> str:
    return f"€ {float(value or 0):,.2f}"


def _expense_label(key: str) -> str:
    return EXPENSE_TYPES.get(key, key)


def _show_image(file_path: str | None):
    if not file_path:
        return
    content = load_file(file_path)
    if not content:
        st.caption("File non disponibile su disco.")
        return
    mime = get_mime_type(file_path)
    if mime == "application/pdf":
        st.download_button("⬇ Scarica PDF originale", content, file_name="ricevuta.pdf", mime=mime)
    else:
        st.image(content, use_container_width=True)


# ─── tabs ─────────────────────────────────────────────────────────────────────

tab_icons = ["📷 Nuovo", "✏️ Revisione", "📋 Archivio", "📊 Dashboard", "💾 Esporta"]
tab_new, tab_review, tab_browse, tab_dash, tab_export = st.tabs(tab_icons)


# ─── TAB 1 · NUOVO SCONTRINO ─────────────────────────────────────────────────

with tab_new:
    st.header("Aggiungi Ricevuta")

    fiscal_year = st.number_input(
        "Anno fiscale", min_value=2020, max_value=_current_year() + 1,
        value=_current_year(), step=1,
    )

    col_cam, col_up = st.columns(2)
    with col_cam:
        camera_file = st.camera_input("📸 Scatta foto")
    with col_up:
        uploaded_file = st.file_uploader(
            "📂 Carica file", type=["jpg", "jpeg", "png", "webp", "pdf"],
            label_visibility="visible",
        )

    source_file = camera_file or uploaded_file
    file_bytes = source_file.getvalue() if source_file else None
    original_name = getattr(source_file, "name", "receipt.jpg") or "receipt.jpg"

    if file_bytes:
        from app.constants import MAX_UPLOAD_BYTES, ALLOWED_EXTENSIONS
        from pathlib import Path as _Path
        _ext_check = _Path(original_name).suffix.lower()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            st.error(f"File troppo grande ({len(file_bytes) // (1024*1024)} MB). Massimo 20 MB.")
        elif _ext_check not in ALLOWED_EXTENSIONS:
            st.error(f"Formato '{_ext_check}' non supportato. Usa JPG, PNG, WebP o PDF.")
        else:
            if not original_name.lower().endswith(".pdf"):
                st.image(file_bytes, use_container_width=True)
            else:
                st.info("PDF caricato.")

            ext = None
            with st.spinner("Analisi automatica in corso..."):
                try:
                    is_pdf = original_name.lower().endswith(".pdf")
                    ext = extract_from_pdf(file_bytes) if is_pdf else extract_from_image(file_bytes)
                except Exception as _exc:
                    st.warning(f"Estrazione automatica non disponibile: {_exc}. Inserisci i dati manualmente.")

            if ext is None:
                from app.schemas import ExtractionResult as _ER
                ext = _ER(confidence=0.0)

            if ext.confidence > 0:
                msg = f"Estrazione completata (confidenza: {ext.confidence*100:.0f}%)"
                if ext.pages_extracted > 1:
                    msg += f" — documento di {ext.pages_extracted} pagine, analizzate le prime 3."
                st.success(msg)
                if ext.tax_deductible is None:
                    st.warning("⚠️ Detraibilità incerta — verifica il campo 'Detraibile 730' prima di salvare.")
            else:
                st.info("Nessuna chiave API OpenAI — inserisci i dati manualmente.")

            st.subheader("Verifica i dati estratti")

            with st.form("new_receipt_form"):
                provider = st.text_input("Fornitore *", value=ext.provider_name or "")
                provider_tax = st.text_input("P.IVA / CF fornitore", value=ext.provider_tax_id or "")

                col1, col2 = st.columns(2)
                with col1:
                    try:
                        _date_val = date.fromisoformat(ext.date) if ext.date else date.today()
                    except ValueError:
                        _date_val = date.today()
                    receipt_date = st.date_input("Data ricevuta", value=_date_val)
                with col2:
                    receipt_num = st.text_input("N. Scontrino/Fattura", value=ext.receipt_number or "")

                exp_type = st.selectbox(
                    "Tipo di spesa *",
                    options=list(EXPENSE_TYPES.keys()),
                    format_func=_expense_label,
                    index=list(EXPENSE_TYPES.keys()).index(ext.expense_type)
                    if ext.expense_type in EXPENSE_TYPES else 0,
                )
                description = st.text_area("Descrizione", value=ext.description or "", height=80)

                col3, col4 = st.columns(2)
                with col3:
                    total = st.number_input(
                        "Importo totale (€) *", min_value=0.0, step=0.01,
                        value=float(ext.total_amount or 0.0), format="%.2f",
                    )
                with col4:
                    ded_default = float(ext.deductible_amount or total or 0.0)
                    deductible = st.number_input(
                        "Importo detraibile (€)", min_value=0.0, step=0.01,
                        value=ded_default, format="%.2f",
                    )

                payment = st.selectbox(
                    "Metodo di pagamento",
                    options=[""] + PAYMENT_METHODS,
                    index=([""] + PAYMENT_METHODS).index(ext.payment_method)
                    if ext.payment_method in PAYMENT_METHODS else 0,
                )

                _ded_options = ["Sì", "No", "Da verificare"]
                if ext.tax_deductible is True:
                    _ded_default_idx = 0
                elif ext.tax_deductible is False:
                    _ded_default_idx = 1
                else:
                    _ded_default_idx = 2
                tax_ded_str = st.selectbox(
                    "Detraibile al 19% (730)",
                    options=_ded_options,
                    index=_ded_default_idx,
                    help="Scegli 'Da verificare' se non sei sicuro — sarà evidenziato nel report 730.",
                )
                tax_ded_value: Optional[bool] = True if tax_ded_str == "Sì" else (False if tax_ded_str == "No" else None)
                notes = st.text_area("Note aggiuntive", height=60)

                submitted = st.form_submit_button("✅ Salva Ricevuta", type="primary")

            if submitted:
                if not provider.strip():
                    st.error("Il campo Fornitore è obbligatorio.")
                else:
                    try:
                        file_path, file_type = save_file(file_bytes, original_name, int(fiscal_year))
                    except ValueError as _ve:
                        st.error(str(_ve))
                        file_path = None
                    except OSError as _oe:
                        st.error(f"Errore di salvataggio file: {_oe}")
                        file_path = None

                    if file_path:
                        data = ReceiptCreate(
                            fiscal_year=int(fiscal_year),
                            date=receipt_date.isoformat(),
                            receipt_number=receipt_num or None,
                            provider_name=provider.strip(),
                            provider_tax_id=provider_tax or None,
                            expense_type=exp_type,
                            description=description or None,
                            payment_method=payment or None,
                            total_amount=total,
                            deductible_amount=deductible if tax_ded_value is True else 0.0,
                            tax_deductible=tax_ded_value,
                            notes=notes or None,
                            original_file_path=file_path,
                            file_type=file_type,
                            raw_extraction=ext.model_dump() if ext.confidence > 0 else None,
                            status="confirmed",
                        )
                        with db() as session:
                            r = create_receipt(session, data)
                        st.success(f"Ricevuta salvata! ID: `{r.id[:8]}…`")
                        st.balloons()


# ─── TAB 2 · REVISIONE PENDENTI ──────────────────────────────────────────────

with tab_review:
    st.header("In Attesa di Revisione")

    with db() as session:
        pending = list_receipts(session, status="pending_review")

    if not pending:
        st.success("Nessuna ricevuta in attesa di revisione.")
    else:
        st.info(f"{len(pending)} ricevuta/e da revisionare")
        for r in pending:
            with st.expander(f"📄 {r.provider_name} — {r.date or 'data?'} — {_format_euro(r.total_amount)}"):
                _show_image(r.original_file_path)
                with st.form(f"review_{r.id}"):
                    provider = st.text_input("Fornitore", value=r.provider_name)
                    provider_tax = st.text_input("P.IVA / CF", value=r.provider_tax_id or "")
                    col1, col2 = st.columns(2)
                    with col1:
                        r_date = st.date_input(
                            "Data",
                            value=date.fromisoformat(r.date) if r.date else date.today(),
                        )
                    with col2:
                        r_num = st.text_input("N. Scontrino", value=r.receipt_number or "")
                    exp_type = st.selectbox(
                        "Tipo", options=list(EXPENSE_TYPES.keys()),
                        format_func=_expense_label,
                        index=list(EXPENSE_TYPES.keys()).index(r.expense_type)
                        if r.expense_type in EXPENSE_TYPES else 0,
                    )
                    desc = st.text_area("Descrizione", value=r.description or "", height=60)
                    col3, col4 = st.columns(2)
                    with col3:
                        total = st.number_input("Importo (€)", value=float(r.total_amount or 0), format="%.2f")
                    with col4:
                        ded = st.number_input("Detraibile (€)", value=float(r.deductible_amount or r.total_amount or 0), format="%.2f")
                    payment = st.selectbox("Pagamento", [""] + PAYMENT_METHODS,
                                           index=([""] + PAYMENT_METHODS).index(r.payment_method)
                                           if r.payment_method in PAYMENT_METHODS else 0)
                    _r_ded_opts = ["Sì", "No", "Da verificare"]
                    _r_ded_idx = 0 if r.tax_deductible is True else (1 if r.tax_deductible is False else 2)
                    tax_ded_str = st.selectbox("Detraibile 730", _r_ded_opts, index=_r_ded_idx)
                    tax_ded_val: Optional[bool] = True if tax_ded_str == "Sì" else (False if tax_ded_str == "No" else None)

                    col_save, col_del = st.columns(2)
                    with col_save:
                        confirmed = st.form_submit_button("✅ Conferma", type="primary")
                    with col_del:
                        discard = st.form_submit_button("🗑 Elimina")

                if confirmed:
                    upd = ReceiptUpdate(
                        provider_name=provider, provider_tax_id=provider_tax or None,
                        date=r_date.isoformat(), receipt_number=r_num or None,
                        expense_type=exp_type, description=desc or None,
                        payment_method=payment or None, total_amount=total,
                        deductible_amount=ded if tax_ded_val is True else 0.0,
                        tax_deductible=tax_ded_val, status="confirmed",
                    )
                    with db() as session:
                        update_receipt(session, r.id, upd)
                    st.success("Confermata!")
                    st.rerun()

                if discard:
                    file_to_del = r.original_file_path
                    with db() as session:
                        delete_receipt(session, r.id)
                    if file_to_del:
                        from app.storage import delete_file as _del_file
                        try:
                            _del_file(file_to_del)
                        except Exception:
                            pass
                    st.warning("Ricevuta eliminata.")
                    st.rerun()


# ─── TAB 3 · ARCHIVIO ────────────────────────────────────────────────────────

with tab_browse:
    st.header("Archivio Ricevute")

    with db() as session:
        years = available_years(session)

    if not years:
        st.info("Nessuna ricevuta ancora salvata.")
    else:
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            sel_year = st.selectbox("Anno", options=years, key="browse_year")
        with col2:
            sel_type = st.selectbox(
                "Tipo", options=["Tutti"] + list(EXPENSE_TYPES.keys()),
                format_func=lambda k: "Tutti" if k == "Tutti" else _expense_label(k),
            )
        with col3:
            search = st.text_input("🔍 Cerca fornitore / descrizione")

        with db() as session:
            receipts = list_receipts(
                session,
                fiscal_year=sel_year,
                expense_type=None if sel_type == "Tutti" else sel_type,
                search=search or None,
                status="confirmed",
            )

        st.caption(f"{len(receipts)} ricevuta/e trovate — totale: {_format_euro(sum(float(r.total_amount or 0) for r in receipts))}")

        for r in receipts:
            with st.expander(
                f"{'✅' if r.status == 'confirmed' else '⏳'} "
                f"{r.date or '—'}  ·  {r.provider_name}  ·  {_format_euro(r.total_amount)}"
                f"  ·  {_expense_label(r.expense_type)}"
            ):
                col_img, col_data = st.columns([1, 1])
                with col_img:
                    _show_image(r.original_file_path)
                with col_data:
                    st.markdown(f"**Fornitore:** {r.provider_name}")
                    if r.provider_tax_id:
                        st.markdown(f"**P.IVA/CF:** {r.provider_tax_id}")
                    st.markdown(f"**Tipo:** {_expense_label(r.expense_type)}")
                    if r.description:
                        st.markdown(f"**Descrizione:** {r.description}")
                    if r.receipt_number:
                        st.markdown(f"**N. Scontrino:** {r.receipt_number}")
                    st.markdown(f"**Importo:** {_format_euro(r.total_amount)}")
                    if r.tax_deductible is True:
                        ded = float(r.deductible_amount or r.total_amount or 0)
                        st.markdown(f"**Detraibile 730:** Sì — {_format_euro(ded)}")
                    elif r.tax_deductible is None:
                        st.markdown("**Detraibile 730:** ⚠️ Da verificare")
                    else:
                        st.markdown("**Detraibile 730:** No")
                    if r.payment_method:
                        st.markdown(f"**Pagamento:** {r.payment_method}")
                    if r.notes:
                        st.markdown(f"**Note:** {r.notes}")

                with st.form(f"edit_{r.id}"):
                    new_notes = st.text_area("Modifica note", value=r.notes or "", height=50)
                    new_provider = st.text_input("Modifica fornitore", value=r.provider_name)
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        save_edit = st.form_submit_button("💾 Salva modifiche")
                    with col_e2:
                        del_btn = st.form_submit_button("🗑 Elimina ricevuta")

                if save_edit:
                    upd = ReceiptUpdate(notes=new_notes or None, provider_name=new_provider)
                    with db() as session:
                        update_receipt(session, r.id, upd)
                    st.success("Aggiornata!")
                    st.rerun()

                if del_btn:
                    file_to_del = r.original_file_path
                    with db() as session:
                        delete_receipt(session, r.id)
                    if file_to_del:
                        from app.storage import delete_file as _del_file2
                        try:
                            _del_file2(file_to_del)
                        except Exception:
                            pass
                    st.warning("Ricevuta eliminata.")
                    st.rerun()


# ─── TAB 4 · DASHBOARD ───────────────────────────────────────────────────────

with tab_dash:
    st.header("Dashboard Spese Sanitarie")

    with db() as session:
        dash_years = available_years(session)

    if not dash_years:
        st.info("Aggiungi le tue prime ricevute per vedere le statistiche.")
    else:
        sel_dash_year = st.selectbox("Anno fiscale", options=dash_years, key="dash_year")

        with db() as session:
            summary = get_dashboard(session, sel_dash_year)

        if summary.pending_review:
            st.warning(f"⚠️ {summary.pending_review} ricevuta/e in attesa di revisione — vai alla tab ✏️ Revisione.")
        if summary.unknown_deductibility:
            st.warning(f"⚠️ {summary.unknown_deductibility} ricevuta/e con detraibilità 'Da verificare' — non incluse nel calcolo 730.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Ricevute", summary.total_receipts)
        c2.metric("Totale spese", _format_euro(summary.total_amount))
        c3.metric("Detrazione stimata 730", _format_euro(summary.estimated_tax_saving))

        st.markdown("---")
        from app.constants import FRANCHISE_EUR
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Totale detraibile lordo:** {_format_euro(summary.total_deductible)}")
            st.markdown(f"**Franchigia 730:** {_format_euro(FRANCHISE_EUR)}")
            taxable = max(0.0, summary.total_deductible - FRANCHISE_EUR)
            st.markdown(f"**Base imponibile:** {_format_euro(taxable)}")
            st.markdown(f"**Detrazione 19%:** {_format_euro(summary.estimated_tax_saving)}")
        with col_b:
            st.caption("_La detrazione effettiva dipende dalla situazione fiscale individuale. Consulta il tuo CAF._")

        if summary.by_type:
            st.markdown("---")
            st.subheader("Spese per categoria")
            try:
                import pandas as pd
                import altair as alt
                chart_data = pd.DataFrame([
                    {"Categoria": _expense_label(k), "Importo (€)": v}
                    for k, v in sorted(summary.by_type.items(), key=lambda x: -x[1])
                ])
                chart = alt.Chart(chart_data).mark_bar(color="#1A73E8").encode(
                    x=alt.X("Importo (€):Q", title="Importo (€)"),
                    y=alt.Y("Categoria:N", sort="-x", title=""),
                    tooltip=["Categoria", "Importo (€)"],
                ).properties(height=min(40 * len(chart_data) + 60, 300))
                st.altair_chart(chart, use_container_width=True)
            except ImportError:
                for k, v in sorted(summary.by_type.items(), key=lambda x: -x[1]):
                    st.markdown(f"- **{_expense_label(k)}:** {_format_euro(v)}")

        with db() as session:
            recent = list_receipts(session, fiscal_year=sel_dash_year, status="confirmed", limit=5)

        if recent:
            st.markdown("---")
            st.subheader("Ultime ricevute")
            for r in recent:
                st.markdown(
                    f"- `{r.date or '—'}` &nbsp; **{r.provider_name}** &nbsp; "
                    f"{_expense_label(r.expense_type)} &nbsp; {_format_euro(r.total_amount)}"
                )


# ─── TAB 5 · ESPORTA ─────────────────────────────────────────────────────────

with tab_export:
    st.header("Esporta Dati")

    with db() as session:
        exp_years = available_years(session)

    if not exp_years:
        st.info("Nessun dato da esportare ancora.")
    else:
        sel_exp_year = st.selectbox("Anno fiscale", options=exp_years, key="exp_year")

        with db() as session:
            export_receipts = list_receipts(session, fiscal_year=sel_exp_year, status="confirmed")

        st.info(f"{len(export_receipts)} ricevuta/e confermate per il {sel_exp_year}")

        col_xl, col_pdf = st.columns(2)

        with col_xl:
            if st.button("📊 Genera Excel", use_container_width=True):
                try:
                    with st.spinner("Generazione Excel..."):
                        xlsx = to_excel(export_receipts, sel_exp_year)
                    st.download_button(
                        "⬇ Scarica Excel",
                        data=xlsx,
                        file_name=f"spese_sanitarie_{sel_exp_year}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                except RuntimeError as e:
                    st.error(f"Errore: {e}. Installa openpyxl.")

        with col_pdf:
            if st.button("📄 Genera PDF", use_container_width=True):
                try:
                    with st.spinner("Generazione PDF..."):
                        pdf_bytes = to_pdf_summary(export_receipts, sel_exp_year)
                    st.download_button(
                        "⬇ Scarica PDF",
                        data=pdf_bytes,
                        file_name=f"spese_sanitarie_{sel_exp_year}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except RuntimeError as e:
                    st.error(f"Errore: {e}. Installa fpdf2.")

        st.markdown("---")
        st.subheader("ℹ️ Come usare per il 730")
        st.markdown("""
1. **Esporta Excel** — contiene tutte le ricevute con importi detraibili
2. Apri il file e verifica il foglio **Riepilogo 730** con la stima della detrazione
3. Consegna il file al tuo **CAF o commercialista** con le ricevute originali
4. La detrazione effettiva (19%) si applica sulla base imponibile dopo la franchigia di **€ 129,11**

> Le immagini originali sono sempre disponibili nell'Archivio per la verifica documentale.
""")
