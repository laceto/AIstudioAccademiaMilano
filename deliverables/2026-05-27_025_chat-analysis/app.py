"""
Chat-to-Insights RSS Pipeline — Streamlit Dashboard
Reads Claude Code sessions, audit logs, and WhatsApp exports as RSS-style feeds.
"""
import sys
from pathlib import Path

# Make scripts/ importable regardless of cwd
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from scripts.chat_analysis.claude_parser import load_claude_feeds, load_audit_feeds
from scripts.chat_analysis.whatsapp_parser import parse_whatsapp_text, load_whatsapp_file
from scripts.chat_analysis.analyzer import analyze_feeds
from scripts.chat_analysis.rss_builder import (
    feed_to_rss, feeds_to_opml, all_feeds_to_rss,
)
from scripts.chat_analysis.models import Feed

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Chat Insights — AI Studio",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Chat-to-Insights RSS Pipeline")
st.caption("Turns Claude Code sessions, audit logs, and WhatsApp chats into RSS-style insights.")

# ── Sidebar: sources ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📥 Data Sources")

    use_audit = st.checkbox("Audit logs (process/audit/)", value=True)
    use_claude_dir = st.checkbox("Claude JSONL sessions (.claude/)", value=True)

    st.divider()
    st.subheader("WhatsApp Export")
    wa_files = st.file_uploader(
        "Upload WhatsApp .txt export(s)",
        type=["txt"],
        accept_multiple_files=True,
        help="Export from WhatsApp: Chat → ⋮ → More → Export Chat → Without Media",
    )

    st.divider()
    st.subheader("Custom JSON feed")
    json_file = st.file_uploader(
        "Upload a JSONL conversation file",
        type=["jsonl", "json"],
        help="Any Claude Code .jsonl session file",
    )

    st.divider()
    top_keywords = st.slider("Top keywords to show", 10, 50, 25)
    max_rss_items = st.slider("Max items in exported RSS", 50, 500, 200)

# ── Load feeds ────────────────────────────────────────────────────────────────
feeds: list[Feed] = []

if use_audit:
    audit_dir = ROOT / "process" / "audit"
    if audit_dir.exists():
        audit_feeds = load_audit_feeds(audit_dir)
        feeds.extend(audit_feeds)
        st.sidebar.success(f"✅ Loaded {len(audit_feeds)} audit logs")
    else:
        st.sidebar.warning("process/audit/ not found")

if use_claude_dir:
    claude_dir = ROOT / ".claude"
    if claude_dir.exists():
        claude_feeds = load_claude_feeds(claude_dir)
        feeds.extend(claude_feeds)
        if claude_feeds:
            st.sidebar.success(f"✅ Loaded {len(claude_feeds)} Claude sessions")
        else:
            st.sidebar.info("No JSONL session files found in .claude/")

for wa_file in wa_files:
    text = wa_file.read().decode("utf-8", errors="replace")
    feed = parse_whatsapp_text(text, source_name=wa_file.name)
    if feed.items:
        feeds.append(feed)
        st.sidebar.success(f"✅ WhatsApp: {wa_file.name} ({feed.item_count} msgs)")
    else:
        st.sidebar.warning(f"⚠️ {wa_file.name}: no messages parsed")

if json_file:
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp.write(json_file.read())
        tmp_path = Path(tmp.name)
    from scripts.chat_analysis.claude_parser import _parse_jsonl_session
    try:
        feed = _parse_jsonl_session(tmp_path)
        feed.title = json_file.name
        if feed.items:
            feeds.append(feed)
            st.sidebar.success(f"✅ JSONL: {json_file.name} ({feed.item_count} items)")
    except Exception as e:
        st.sidebar.error(f"Failed to parse JSONL: {e}")
    finally:
        os.unlink(tmp_path)

# ── Guard: no feeds ───────────────────────────────────────────────────────────
if not feeds:
    st.info(
        "No data loaded yet.\n\n"
        "**Options:**\n"
        "- Enable 'Audit logs' in the sidebar (they're already in the repo)\n"
        "- Upload a WhatsApp `.txt` export\n"
        "- Upload a Claude Code `.jsonl` session file"
    )
    st.stop()

# ── Run analysis ──────────────────────────────────────────────────────────────
insights = analyze_feeds(feeds)

if "error" in insights:
    st.error(insights["error"])
    st.stop()

summary = insights["summary"]

# ── Summary KPIs ──────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Feeds / Channels", summary["feed_count"])
c2.metric("Total Messages", f"{summary['message_count']:,}")
c3.metric("Total Words", f"{summary['total_words']:,}")
c4.metric("Avg Words/Msg", summary["avg_words_per_message"])
c5.metric("Source Types", len(summary["source_types"]))

dr = summary["date_range"]
st.caption(
    f"Date range: **{dr['first'][:10]}** → **{dr['last'][:10]}**  |  "
    f"Source types: {', '.join(summary['source_types'])}"
)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_kw, tab_timeline, tab_heat, tab_authors, tab_feeds, tab_export = st.tabs([
    "🔑 Keywords", "📅 Timeline", "⏰ Activity Heatmap",
    "👤 Authors", "📋 Feeds", "📤 Export RSS",
])

# ── Keywords tab ──────────────────────────────────────────────────────────────
with tab_kw:
    st.subheader("Top Keywords Across All Feeds")
    kw_data = insights["keywords"][:top_keywords]
    if kw_data:
        df_kw = pd.DataFrame(kw_data, columns=["keyword", "count"])
        st.bar_chart(df_kw.set_index("keyword")["count"])

        st.subheader("Sentiment Proxy")
        sent = insights["sentiment"]
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Positive", f"{sent['positive']:.1%}")
        sc2.metric("Negative", f"{sent['negative']:.1%}")
        sc3.metric("Neutral", f"{sent['neutral']:.1%}")

        if len(feeds) > 1:
            st.subheader("Per-Feed Top Keywords")
            pfk = insights["per_feed_keywords"]
            rows = []
            for feed in feeds[:15]:
                kws = pfk.get(feed.id, [])
                rows.append({"Feed": feed.title[:40], "Top Keywords": ", ".join(kws[:8])})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Timeline tab ──────────────────────────────────────────────────────────────
with tab_timeline:
    st.subheader("Message Activity by Day")
    abd = insights["activity_by_day"]
    if abd:
        df_time = pd.DataFrame(
            [(d, c) for d, c in abd.items()],
            columns=["date", "messages"],
        )
        df_time["date"] = pd.to_datetime(df_time["date"])
        df_time = df_time.set_index("date").sort_index()
        st.line_chart(df_time["messages"])

        # Rolling 7-day average
        df_time["7d_avg"] = df_time["messages"].rolling(7, min_periods=1).mean()
        st.area_chart(df_time[["messages", "7d_avg"]])

# ── Hourly heatmap tab ────────────────────────────────────────────────────────
with tab_heat:
    st.subheader("Messages by Hour of Day")
    hh = insights["hourly_heatmap"]
    if hh:
        df_hour = pd.DataFrame(
            [(h, c) for h, c in hh.items()],
            columns=["hour", "messages"],
        ).set_index("hour").sort_index()
        st.bar_chart(df_hour["messages"])
        peak_hour = max(hh, key=hh.get)
        st.caption(f"Peak activity at **{peak_hour:02d}:00** with {hh[peak_hour]} messages.")

# ── Authors tab ───────────────────────────────────────────────────────────────
with tab_authors:
    st.subheader("Author Breakdown")
    authors = insights["authors"]
    if authors:
        df_auth = pd.DataFrame(authors)
        st.dataframe(df_auth, use_container_width=True, hide_index=True)
        st.bar_chart(df_auth.set_index("author")["messages"].head(20))

# ── Feeds tab ─────────────────────────────────────────────────────────────────
with tab_feeds:
    st.subheader("Feed Inventory (RSS Channels)")
    feed_rows = insights["feeds"]
    if feed_rows:
        df_feeds = pd.DataFrame(feed_rows)
        st.dataframe(df_feeds, use_container_width=True, hide_index=True)

    st.subheader("Browse a Feed")
    feed_titles = {f.title: f for f in feeds}
    selected_title = st.selectbox("Select feed", list(feed_titles.keys()))
    if selected_title:
        sel_feed = feed_titles[selected_title]
        st.caption(f"{sel_feed.description}  |  {sel_feed.item_count} messages")
        items_df = pd.DataFrame([
            {
                "timestamp": i.timestamp.isoformat()[:19],
                "author": i.author,
                "words": i.word_count,
                "preview": i.content[:120].replace("\n", " "),
            }
            for i in sorted(sel_feed.items, key=lambda x: x.timestamp, reverse=True)
        ])
        st.dataframe(items_df, use_container_width=True, hide_index=True)

# ── Export tab ────────────────────────────────────────────────────────────────
with tab_export:
    st.subheader("Export as RSS / OPML")

    col_rss, col_opml = st.columns(2)

    with col_rss:
        st.markdown("**Merged RSS 2.0** (all feeds, most recent items)")
        rss_bytes = all_feeds_to_rss(feeds, top_n=max_rss_items)
        st.download_button(
            "⬇️ Download merged.rss",
            data=rss_bytes,
            file_name="aistudio_chats_merged.rss",
            mime="application/rss+xml",
        )

        st.markdown("**Per-feed RSS** — choose a channel:")
        feed_titles_list = [f.title for f in feeds]
        sel = st.selectbox("Feed for individual RSS export", feed_titles_list, key="rss_sel")
        if sel:
            chosen_feed = {f.title: f for f in feeds}[sel]
            per_rss = feed_to_rss(chosen_feed)
            st.download_button(
                f"⬇️ Download {chosen_feed.id}.rss",
                data=per_rss,
                file_name=f"{chosen_feed.id}.rss",
                mime="application/rss+xml",
            )

    with col_opml:
        st.markdown("**OPML** (import into any RSS reader: Feedly, NewsBlur, etc.)")
        opml_bytes = feeds_to_opml(feeds)
        st.download_button(
            "⬇️ Download feeds.opml",
            data=opml_bytes,
            file_name="aistudio_feeds.opml",
            mime="text/x-opml",
        )

    st.divider()
    st.subheader("Raw Insights JSON")
    with st.expander("View full insights payload"):
        # Convert non-serializable objects
        safe = json.loads(json.dumps(insights, default=str))
        st.json(safe)
    st.download_button(
        "⬇️ Download insights.json",
        data=json.dumps(insights, default=str, indent=2).encode(),
        file_name="chat_insights.json",
        mime="application/json",
    )
