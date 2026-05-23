"""
AI Studio Knowledge Search — Streamlit UI

Search the entire codebase, agent specs, and process docs with natural
language. Powered by sentence-transformers (local) or OpenAI embeddings.

Deploy: streamlit run deliverables/rag/streamlit_rag_app.py
"""

import sys
from pathlib import Path

import streamlit as st

# Ensure repo root is on path when running via streamlit
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="AI Studio Knowledge Search", page_icon="🔍", layout="wide")

st.title("🔍 AI Studio Accademia Milano — Knowledge Search")
st.caption("Semantic search over all code, agent specs, process docs, and community guides.")

# Sidebar
with st.sidebar:
    st.header("Settings")
    top_k = st.slider("Top-K results", 1, 20, 5)
    show_score = st.checkbox("Show similarity score", value=True)
    show_full_text = st.checkbox("Show full chunk text", value=False)
    st.divider()
    st.markdown(
        "**Index must be built first:**\n"
        "```\npython -m scripts.embed_index\n```"
    )

# Query input
query = st.text_input(
    "Search",
    placeholder="e.g. how does the invoice template work? what agents review risk?",
)

if query:
    try:
        from scripts.retrieve import retrieve, format_results  # noqa: E402

        with st.spinner("Searching..."):
            results = retrieve(query, top_k=top_k)

        if not results:
            st.warning("No results found. Check that the index is built.")
        else:
            for i, r in enumerate(results, 1):
                with st.expander(
                    f"{'#' + str(i)} `{r['source']}` "
                    + (f"— score {r['score']:.3f}" if show_score else ""),
                    expanded=(i == 1),
                ):
                    if show_full_text:
                        st.code(r["text"], language="text")
                    else:
                        st.code(r["text"][:400] + ("..." if len(r["text"]) > 400 else ""), language="text")
                    st.caption(f"File type: `{r['file_type']}` | Chunk: {r['chunk_index']}")
    except FileNotFoundError as e:
        st.error(str(e))
    except ImportError as e:
        st.error(f"Missing dependency: {e}. Run `pip install -r requirements-rag.txt`")
