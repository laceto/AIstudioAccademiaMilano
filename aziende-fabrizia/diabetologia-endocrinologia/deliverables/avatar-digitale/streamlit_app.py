"""
Avatar Digitale — Dott.ssa Fabrizia Aceto
Dashboard Streamlit: gestione community, digest, bozze post, sync Google Drive.
"""
import os
import json
from datetime import datetime
import streamlit as st
from openai import OpenAI

from chat_organizer import (
    parse_whatsapp_export,
    categorize_messages,
    generate_daily_digest,
)
from avatar_persona import (
    draft_community_reply,
    draft_linkedin_post,
    draft_group_summary_post,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Avatar Digitale · Dott.ssa Fabrizia",
    page_icon="👩‍⚕️",
    layout="wide",
)

st.markdown("""
<style>
.priority-alta  {border-left:4px solid #ef4444; padding:8px 12px; background:#fef2f2; border-radius:0 6px 6px 0; margin:4px 0;}
.priority-media {border-left:4px solid #f59e0b; padding:8px 12px; background:#fffbeb; border-radius:0 6px 6px 0; margin:4px 0;}
.priority-bassa {border-left:4px solid #22c55e; padding:8px 12px; background:#f0fdf4; border-radius:0 6px 6px 0; margin:4px 0;}
.draft-box {background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:1rem; margin:8px 0;}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
col_title, col_date = st.columns([3, 1])
with col_title:
    st.title("👩‍⚕️ Avatar Digitale — Fabrizia")
    st.caption("Diabetologa & Endocrinologa · Gestione Community & Presenza Digitale")
with col_date:
    st.metric("Oggi", datetime.now().strftime("%d %b %Y"))

st.markdown("---")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurazione")

    api_key = st.text_input(
        "OpenAI API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
    )

    st.markdown("---")
    st.subheader("📱 Telegram")
    use_telegram = st.checkbox("Usa Telegram live", value=False)
    if use_telegram:
        tg_api_id   = st.text_input("API ID",   value=os.getenv("TELEGRAM_API_ID", ""))
        tg_api_hash = st.text_input("API Hash", value=os.getenv("TELEGRAM_API_HASH", ""), type="password")
        tg_hours    = st.slider("Ultime N ore", 1, 72, 24)

    st.markdown("---")
    st.subheader("☁️ Google Drive")
    use_drive = st.checkbox("Sync Google Drive", value=False)
    if use_drive:
        st.caption("Richiede credentials.json nella stessa cartella")

    st.markdown("---")
    st.caption("**Community di Fabrizia**")
    st.caption("• SID — Società Italiana Diabetologia")
    st.caption("• AMD — Assoc. Medici Diabetologi")
    st.caption("• AME — Assoc. Medici Endocrinologi")
    st.caption("• SIE — Soc. Italiana Endocrinologia")
    st.caption("• Medylink (social medici IT)")
    st.caption("• Gruppi Telegram specialistici")

# ── Tabs principali ────────────────────────────────────────────────────────────
tab_digest, tab_wa, tab_avatar, tab_linkedin, tab_drive = st.tabs([
    "📋 Digest Giornaliero",
    "💬 Chat Organizer",
    "🤖 Avatar Risponde",
    "💼 LinkedIn Post",
    "☁️ Google Drive",
])

# ────────────────────────────────────────────────────────────────────────────────
# TAB 1 — Digest Giornaliero
# ────────────────────────────────────────────────────────────────────────────────
with tab_digest:
    st.subheader("Digest Giornaliero Community")

    input_method = st.radio(
        "Sorgente dati",
        ["Carica JSON snapshot", "Usa Telegram live", "Inserisci manualmente"],
        horizontal=True,
    )

    groups_data = []

    if input_method == "Carica JSON snapshot":
        uploaded = st.file_uploader("Carica snapshot JSON (generato da sessione precedente)", type="json")
        if uploaded:
            groups_data = json.load(uploaded)
            st.success(f"Caricati {len(groups_data)} gruppi")

    elif input_method == "Usa Telegram live":
        if use_telegram and tg_api_id and tg_api_hash:
            if st.button("📥 Scarica da Telegram ora"):
                os.environ["TELEGRAM_API_ID"]   = tg_api_id
                os.environ["TELEGRAM_API_HASH"] = tg_api_hash
                with st.spinner("Connessione a Telegram..."):
                    try:
                        from telegram_reader import run_fetch
                        raw = run_fetch(since_hours=tg_hours)
                        if api_key:
                            client = OpenAI(api_key=api_key)
                            for group_name, messages in raw.items():
                                cat = categorize_messages(messages, client, group_name)
                                groups_data.append(cat)
                            st.success(f"Scaricati e analizzati {len(groups_data)} gruppi")
                    except Exception as e:
                        st.error(f"Errore Telegram: {e}")
        else:
            st.info("Configura Telegram nella sidebar e abilita la checkbox.")

    else:
        st.info("Inserisci manualmente i dati dei gruppi (funzione avanzata — usa WhatsApp export)")

    if st.button("🧠 Genera Digest AI", type="primary", disabled=(not api_key or not groups_data)):
        client = OpenAI(api_key=api_key)
        with st.spinner("Generazione digest in corso..."):
            digest = generate_daily_digest(
                groups_data, client,
                date_str=datetime.now().strftime("%d %B %Y"),
            )
        st.session_state["digest"] = digest

    if "digest" in st.session_state:
        st.markdown(st.session_state["digest"])
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Scarica Digest (.md)",
                data=st.session_state["digest"],
                file_name=f"Digest_{datetime.now().strftime('%Y-%m-%d')}.md",
                mime="text/markdown",
            )
        with col2:
            if use_drive and st.button("☁️ Salva su Google Drive"):
                try:
                    from gdrive_sync import save_daily_digest
                    link = save_daily_digest(st.session_state["digest"])
                    st.success(f"[Apri su Drive]({link})")
                except Exception as e:
                    st.error(f"Errore Drive: {e}")

# ────────────────────────────────────────────────────────────────────────────────
# TAB 2 — Chat Organizer (WhatsApp export)
# ────────────────────────────────────────────────────────────────────────────────
with tab_wa:
    st.subheader("Organizzatore Chat WhatsApp")
    st.caption(
        "Esporta una chat WhatsApp: "
        "**Apri chat → ⋮ → Esporta chat → Senza media** → carica il .txt qui"
    )

    uploaded_chats = st.file_uploader(
        "Carica export WhatsApp (.txt)",
        type="txt",
        accept_multiple_files=True,
    )

    if uploaded_chats and api_key:
        client = OpenAI(api_key=api_key)
        all_analyzed = []

        with st.spinner(f"Analisi di {len(uploaded_chats)} chat..."):
            for f in uploaded_chats:
                text = f.read().decode("utf-8", errors="ignore")
                messages = parse_whatsapp_export(text)
                if messages:
                    result = categorize_messages(messages, client, group_name=f.name.replace(".txt", ""))
                    all_analyzed.append(result)

        st.session_state["wa_analyzed"] = all_analyzed
        st.success(f"Analizzate {len(all_analyzed)} chat")

    if "wa_analyzed" in st.session_state:
        for group in st.session_state["wa_analyzed"]:
            priority = group.get("priorita", "bassa").lower()
            css_class = f"priority-{priority}"

            with st.expander(
                f"{'🔴' if priority=='alta' else '🟡' if priority=='media' else '🟢'} "
                f"{group.get('group_name', 'Chat')} "
                f"— {group.get('topic_principale', '?')} "
                f"({group.get('total_messages', 0)} msg)"
            ):
                st.markdown(
                    f"<div class='{css_class}'>{group.get('sintesi', '')}</div>",
                    unsafe_allow_html=True,
                )
                col_l, col_r = st.columns(2)
                with col_l:
                    if group.get("argomenti_trattati"):
                        st.markdown("**Argomenti**")
                        for a in group["argomenti_trattati"]:
                            st.markdown(f"• {a}")
                with col_r:
                    if group.get("azioni_richieste"):
                        st.markdown("**Azioni richieste**")
                        for az in group["azioni_richieste"]:
                            st.markdown(f"→ {az}")
                if group.get("messaggi_rilevanti"):
                    st.markdown("**Messaggi chiave**")
                    for mr in group["messaggi_rilevanti"]:
                        st.markdown(
                            f"> *{mr.get('sender','?')}*: "
                            f"{mr.get('text','')[:200]}  \n"
                            f"↳ {mr.get('motivo','')}"
                        )

                if use_drive and st.button(f"☁️ Salva su Drive", key=f"drive_{group.get('group_name','')}"):
                    try:
                        from gdrive_sync import save_community_snapshot
                        link = save_community_snapshot(
                            json.dumps(group, ensure_ascii=False, indent=2),
                            group.get("group_name", "chat"),
                        )
                        st.success(f"[Apri su Drive]({link})")
                    except Exception as e:
                        st.error(f"Errore Drive: {e}")

# ────────────────────────────────────────────────────────────────────────────────
# TAB 3 — Avatar Risponde
# ────────────────────────────────────────────────────────────────────────────────
with tab_avatar:
    st.subheader("Avatar Risponde — Bozze nel Tuo Stile")

    col_msg, col_ctx = st.columns([2, 1])
    with col_msg:
        original_msg = st.text_area(
            "Incolla il messaggio a cui rispondere",
            height=120,
            placeholder="Es: Ciao Fabrizia, ho un paziente T2DM con HbA1c 9.2 nonostante metformina 2g. Come ti comporti?",
        )
    with col_ctx:
        group_ctx = st.text_input("Contesto gruppo", placeholder="Es: Gruppo diabetologi SID")
        reply_style = st.selectbox(
            "Stile risposta",
            ["collegiale", "formale", "didattico"],
            format_func=lambda x: {"collegiale": "Colloquiale tra colleghi", "formale": "Formale/istituzionale", "didattico": "Didattico/educativo"}[x]
        )

    if st.button("✍️ Genera Bozza Risposta", type="primary", disabled=(not api_key or not original_msg)):
        client = OpenAI(api_key=api_key)
        with st.spinner("Generazione risposta..."):
            draft = draft_community_reply(original_msg, group_ctx, client, style=reply_style)
        st.session_state["draft_reply"] = draft

    if "draft_reply" in st.session_state:
        st.markdown("**Bozza generata:**")
        st.markdown(f'<div class="draft-box">{st.session_state["draft_reply"]}</div>', unsafe_allow_html=True)
        col_copy, col_save = st.columns(2)
        with col_copy:
            st.text_area("Copia da qui", value=st.session_state["draft_reply"], height=150)
        with col_save:
            if use_drive and st.button("☁️ Salva bozza su Drive"):
                try:
                    from gdrive_sync import save_draft_post
                    link = save_draft_post(st.session_state["draft_reply"], "telegram", "reply")
                    st.success(f"[Apri su Drive]({link})")
                except Exception as e:
                    st.error(f"Errore Drive: {e}")

# ────────────────────────────────────────────────────────────────────────────────
# TAB 4 — LinkedIn Post
# ────────────────────────────────────────────────────────────────────────────────
with tab_linkedin:
    st.subheader("Generatore Post LinkedIn — Voce di Fabrizia")

    col_topic, col_type = st.columns([2, 1])
    with col_topic:
        topic = st.text_area(
            "Argomento / fonte / spunto",
            height=100,
            placeholder="Es: Studio su Lancet Diabetes 2025 che mostra riduzione HbA1c con semaglutide 2mg vs 1mg",
        )
    with col_type:
        post_type = st.selectbox(
            "Tipo di post",
            ["insight_clinico", "aggiornamento_ricerca", "riflessione_professionale", "caso_anonimizzato"],
            format_func=lambda x: {
                "insight_clinico":        "💡 Insight clinico",
                "aggiornamento_ricerca":  "📄 Update ricerca",
                "riflessione_professionale": "🧠 Riflessione",
                "caso_anonimizzato":      "🔬 Caso clinico anonimo",
            }[x]
        )
        source_ref = st.text_input("Riferimento/link fonte", placeholder="es. Lancet Diabetes 2025")

    if st.button("✍️ Genera Post LinkedIn", type="primary", disabled=(not api_key or not topic)):
        client = OpenAI(api_key=api_key)
        full_topic = f"{topic}\nFonte: {source_ref}" if source_ref else topic
        with st.spinner("Generazione post..."):
            post = draft_linkedin_post(full_topic, source_ref, client, post_type=post_type)
        st.session_state["li_post"] = post

    if "li_post" in st.session_state:
        st.markdown("**Bozza LinkedIn:**")
        st.text_area("Bozza (copia su LinkedIn):", value=st.session_state["li_post"], height=300)
        char_count = len(st.session_state["li_post"])
        st.caption(f"Caratteri: {char_count} / 3000")
        if char_count > 3000:
            st.warning("Post troppo lungo per LinkedIn (max 3000 caratteri)")
        if use_drive and st.button("☁️ Salva post su Drive"):
            try:
                from gdrive_sync import save_draft_post
                slug = topic[:30].replace(" ", "_")
                link = save_draft_post(st.session_state["li_post"], "linkedin", slug)
                st.success(f"[Apri su Drive]({link})")
            except Exception as e:
                st.error(f"Errore Drive: {e}")

# ────────────────────────────────────────────────────────────────────────────────
# TAB 5 — Google Drive
# ────────────────────────────────────────────────────────────────────────────────
with tab_drive:
    st.subheader("☁️ Google Drive — Archivio Digitale Fabrizia")
    st.markdown("""
**Struttura cartelle su Drive:**
```
Fabrizia — Avatar Digitale/
├── Digest Giornalieri/     ← digest .md per ogni giorno
├── Community Snapshots/    ← JSON dei gruppi analizzati
└── Bozze Post/             ← draft LinkedIn, Telegram
```
    """)

    if use_drive:
        st.info("Google Drive abilitato. Usa i bottoni '☁️ Salva su Drive' nelle altre tab.")
        if st.button("🔍 Verifica connessione Drive"):
            try:
                from gdrive_sync import _get_service, _ensure_folder_structure
                svc = _get_service()
                folders = _ensure_folder_structure(svc)
                st.success("Connessione OK. Struttura cartelle verificata.")
                st.json(folders)
            except Exception as e:
                st.error(f"Errore connessione Drive: {e}")
                st.caption("Verifica che credentials.json sia nella stessa cartella dell'app.")
    else:
        st.info("Abilita 'Sync Google Drive' nella sidebar per usare questa funzione.")

    st.markdown("---")
    st.markdown("**Setup Google Drive (una tantum):**")
    st.code("""
1. console.cloud.google.com → Nuovo progetto
2. Abilita "Google Drive API"
3. Credenziali → Crea credenziali → App desktop → scarica credentials.json
4. Metti credentials.json nella stessa cartella di streamlit_app.py
5. Prima esecuzione: si apre browser per autorizzazione
    """, language="text")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "**Avatar Digitale** — Dott.ssa Fabrizia Aceto | "
    "AI: OpenAI GPT-4o | "
    "Ogni output richiede revisione e approvazione prima dell'invio."
)
