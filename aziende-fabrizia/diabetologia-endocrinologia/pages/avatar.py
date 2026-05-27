import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deliverables', 'avatar-digitale'))

import json
import streamlit as st
from openai import OpenAI
from chat_organizer import parse_whatsapp_export, categorize_messages, generate_daily_digest
from avatar_persona import draft_community_reply, draft_linkedin_post

st.title("👤 Avatar & Community")
st.caption("Organizza le tue chat · Rispondi come Fabrizia · Crea post LinkedIn")

with st.sidebar:
    api_key   = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY",""), type="password")
    use_drive = st.checkbox("Sync Google Drive", value=False)
    if use_drive:
        st.caption("Richiede `credentials.json` nella cartella radice")
    st.markdown("---")
    st.caption("**Community di Fabrizia**")
    for c in ["SID — Diabetologia","AMD — Medici Diabetologi",
              "AME — Medici Endocrinologi","SIE — Endocrinologia",
              "Medylink","Gruppi Telegram specialistici"]:
        st.caption(f"• {c}")

tab_wa, tab_reply, tab_li, tab_digest = st.tabs([
    "💬 Chat WhatsApp", "✍️ Rispondi", "💼 LinkedIn", "📋 Digest"
])

# ── Tab 1: WhatsApp organizer ────────────────────────────────────────────────
with tab_wa:
    st.subheader("Organizza Export WhatsApp")
    st.caption("**Come esportare:** Apri chat → ⋮ → Esporta chat → Senza media → carica .txt")
    files = st.file_uploader("Carica export .txt (anche più file)", type="txt", accept_multiple_files=True)

    if files and api_key and st.button("🧠 Analizza chat", type="primary"):
        client   = OpenAI(api_key=api_key)
        analyzed = []
        prog     = st.progress(0, "Analisi in corso...")
        for i, f in enumerate(files):
            text = f.read().decode("utf-8", errors="ignore")
            msgs = parse_whatsapp_export(text)
            if msgs:
                res = categorize_messages(msgs, client, f.name.replace(".txt",""))
                analyzed.append(res)
            prog.progress((i+1)/len(files))
        prog.empty()
        st.session_state["wa_groups"] = analyzed

    elif files and not api_key:
        st.warning("Inserisci OpenAI API Key nella sidebar.")

    if "wa_groups" in st.session_state:
        groups = st.session_state["wa_groups"]
        p_icon = {"alta":"🔴","media":"🟡","bassa":"🟢"}
        for g in groups:
            pri  = (g.get("priorita") or "bassa").lower()
            icon = p_icon.get(pri, "⚪")
            with st.expander(f"{icon} {g.get('group_name','')} — {g.get('topic_principale','')} ({g.get('total_messages',0)} msg)"):
                st.info(g.get("sintesi",""))
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Argomenti**")
                    for a in g.get("argomenti_trattati",[]): st.markdown(f"• {a}")
                with c2:
                    st.markdown("**Azioni richieste**")
                    for az in g.get("azioni_richieste",[]): st.markdown(f"→ {az}")
                if use_drive and st.button("☁️ Salva su Drive", key=f"dr_{g.get('group_name','')}"):
                    try:
                        from gdrive_sync import save_community_snapshot
                        link = save_community_snapshot(json.dumps(g, ensure_ascii=False, indent=2), g.get("group_name",""))
                        st.success(f"[Apri su Drive]({link})")
                    except Exception as e:
                        st.error(str(e))

# ── Tab 2: Rispondi ──────────────────────────────────────────────────────────
with tab_reply:
    st.subheader("Bozza risposta nel tuo stile")
    msg = st.text_area("Messaggio a cui rispondere", height=100,
                       placeholder="Es: Ciao Fabrizia, che pensi dell'uso di semaglutide in T2DM con BMI 28?")
    ctx   = st.text_input("Contesto gruppo", placeholder="Es: Gruppo diabetologi SID")
    style = st.radio("Stile", ["collegiale","formale","didattico"], horizontal=True,
                     format_func=lambda x: {"collegiale":"👥 Collegiale","formale":"🎩 Formale","didattico":"📚 Didattico"}[x])

    if st.button("✍️ Genera bozza", type="primary", disabled=(not api_key or not msg)):
        client = OpenAI(api_key=api_key)
        with st.spinner("..."):
            draft = draft_community_reply(msg, ctx, client, style=style)
        st.session_state["draft_reply"] = draft

    if "draft_reply" in st.session_state:
        st.text_area("Bozza (copia da qui):", value=st.session_state["draft_reply"], height=180)
        if use_drive and st.button("☁️ Salva bozza su Drive"):
            try:
                from gdrive_sync import save_draft_post
                link = save_draft_post(st.session_state["draft_reply"], "telegram", "reply")
                st.success(f"[Apri su Drive]({link})")
            except Exception as e:
                st.error(str(e))

# ── Tab 3: LinkedIn ──────────────────────────────────────────────────────────
with tab_linkedin:
    st.subheader("Post LinkedIn — voce di Fabrizia")
    topic = st.text_area("Argomento / spunto / paper", height=90,
                         placeholder="Es: Studio su Lancet 2025: semaglutide 2mg riduce HbA1c di 1.8% vs placebo")
    tipo  = st.selectbox("Tipo",
                         ["insight_clinico","aggiornamento_ricerca","riflessione_professionale","caso_anonimizzato"],
                         format_func=lambda x: {"insight_clinico":"💡 Insight clinico","aggiornamento_ricerca":"📄 Update ricerca",
                                                "riflessione_professionale":"🧠 Riflessione","caso_anonimizzato":"🔬 Caso anonimo"}[x])
    fonte = st.text_input("Fonte / riferimento", placeholder="es. Lancet Diabetes & Endocrinology 2025")

    if st.button("✍️ Genera post", type="primary", disabled=(not api_key or not topic)):
        client = OpenAI(api_key=api_key)
        with st.spinner("Generazione post LinkedIn..."):
            post = draft_linkedin_post(f"{topic}\nFonte: {fonte}", fonte, client, post_type=tipo)
        st.session_state["li_post"] = post

    if "li_post" in st.session_state:
        st.text_area("Bozza (copia su LinkedIn):", value=st.session_state["li_post"], height=280)
        n = len(st.session_state["li_post"])
        st.caption(f"{n}/3000 caratteri")
        if n > 3000: st.warning("Troppo lungo per LinkedIn (max 3000 caratteri)")
        if use_drive and st.button("☁️ Salva post su Drive"):
            try:
                from gdrive_sync import save_draft_post
                link = save_draft_post(st.session_state["li_post"], "linkedin", topic[:30])
                st.success(f"[Apri su Drive]({link})")
            except Exception as e:
                st.error(str(e))

# ── Tab 4: Digest ────────────────────────────────────────────────────────────
with tab_digest:
    st.subheader("Digest giornaliero")
    st.caption("Genera un digest AI dai gruppi già analizzati nella tab Chat WhatsApp.")
    if "wa_groups" in st.session_state and api_key:
        if st.button("📋 Genera digest", type="primary"):
            client = OpenAI(api_key=api_key)
            with st.spinner("Generazione digest..."):
                from datetime import datetime
                digest = generate_daily_digest(st.session_state["wa_groups"], client,
                                               date_str=datetime.now().strftime("%d %B %Y"))
            st.markdown(digest)
            st.download_button("⬇️ Scarica digest", digest,
                               f"digest_{datetime.now().strftime('%Y-%m-%d')}.md", "text/markdown")
            if use_drive and st.button("☁️ Salva su Drive"):
                try:
                    from gdrive_sync import save_daily_digest
                    link = save_daily_digest(digest)
                    st.success(f"[Apri su Drive]({link})")
                except Exception as e:
                    st.error(str(e))
    else:
        st.info("Prima analizza le chat nella tab **Chat WhatsApp**, poi torna qui.")
