"""
Studio Digitale — Dott.ssa Fabrizia Aceto
Unico punto di accesso a tutti gli strumenti.

Avvio:
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Studio Fabrizia",
    page_icon="👩‍⚕️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/home.py",   title="Home",              icon="🏠", default=True),
    st.Page("pages/radar.py",  title="Research Radar",    icon="🛰️"),
    st.Page("pages/pubmed.py", title="PubMed AI",         icon="🔬"),
    st.Page("pages/meta.py",   title="Meta-Analysis",     icon="📊"),
    st.Page("pages/avatar.py", title="Avatar & Community",icon="👤"),
])
pg.run()
