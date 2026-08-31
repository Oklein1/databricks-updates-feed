"""
Databricks News — a Hacker-News-style Streamlit reader for the Databricks
docs release-notes RSS feed (https://docs.databricks.com/aws/en/feed.xml).

Run with:
    streamlit run app.py
"""
from datetime import datetime, timezone

import streamlit as st

from scripts.fetch_feed import FEED_URL, fetch_items

st.set_page_config(
    page_title="Databricks News",
    page_icon="🧱",
    layout="centered",
)

# ---------------------------------------------------------------- styling --
st.markdown(
    """
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .block-container {padding-top: 1.2rem; max-width: 780px;}

        .hn-topbar {
            background: #ff6600;
            color: white;
            padding: 8px 14px;
            border-radius: 3px;
            font-weight: 700;
            font-size: 1.05rem;
            margin-bottom: 4px;
        }
        .hn-topbar span.sub {
            font-weight: 400;
            font-size: 0.85rem;
            opacity: 0.9;
        }
        .hn-row {
            display: flex;
            gap: 8px;
            padding: 7px 2px;
            border-bottom: 1px solid #f0f0ef;
        }
        .hn-rank {
            color: #828282;
            font-size: 0.95rem;
            min-width: 22px;
            text-align: right;
        }
        .hn-title a {
            color: #1a1a1a;
            text-decoration: none;
            font-size: 1.0rem;
            font-weight: 600;
        }
        .hn-title a:hover { text-decoration: underline; }
        .hn-domain {
            color: #828282;
            font-size: 0.78rem;
        }
        .hn-meta {
            color: #828282;
            font-size: 0.78rem;
            margin-top: 2px;
        }
        .hn-badge {
            display: inline-block;
            background: #fff6ee;
            color: #ff6600;
            border: 1px solid #ffd9b3;
            border-radius: 3px;
            padding: 0 5px;
            font-size: 0.72rem;
            margin-right: 6px;
        }
        .hn-summary {
            color: #4a4a4a;
            font-size: 0.85rem;
            margin-top: 4px;
            line-height: 1.35;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data ----
@st.cache_data(ttl=900, show_spinner="Fetching latest Databricks updates…")
def load_items():
    return fetch_items(FEED_URL)


def time_ago(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts)
    except ValueError:
        return iso_ts
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


# ---------------------------------------------------------------- header --
st.markdown(
    '<div class="hn-topbar">🧱 Databricks News '
    '<span class="sub">&nbsp;| release notes, straight from the docs feed</span></div>',
    unsafe_allow_html=True,
)

try:
    items = load_items()
    fetch_error = None
except Exception as exc:  # noqa: BLE001
    items = []
    fetch_error = str(exc)

if fetch_error:
    st.error(f"Couldn't fetch the feed right now: {fetch_error}")
    st.stop()

categories = ["All"] + sorted({item["category"] for item in items})

top = st.columns([3, 2, 1])
with top[0]:
    query = st.text_input("Search", placeholder="Search titles & summaries…", label_visibility="collapsed")
with top[1]:
    category = st.selectbox("Category", categories, label_visibility="collapsed")
with top[2]:
    if st.button("↻ Refresh", use_container_width=True):
        load_items.clear()
        st.rerun()

filtered = items
if category != "All":
    filtered = [i for i in filtered if i["category"] == category]
if query:
    q = query.lower()
    filtered = [
        i for i in filtered
        if q in i["title"].lower() or q in i["summary"].lower()
    ]

st.caption(f"{len(filtered)} of {len(items)} updates · source: {FEED_URL}")
st.write("")

if not filtered:
    st.info("No updates match your filters.")

for rank, item in enumerate(filtered, start=1):
    with st.container():
        cols = st.columns([1, 20])
        with cols[0]:
            st.markdown(f'<div class="hn-rank">{rank}.</div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(
                f"""
                <div class="hn-title"><a href="{item['link']}" target="_blank">{item['title']}</a></div>
                <div class="hn-domain">({item['domain']})</div>
                <div class="hn-meta">
                    <span class="hn-badge">{item['category']}</span>
                    {time_ago(item['published'])}
                </div>
                <div class="hn-summary">{item['summary']}</div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('<hr style="margin:6px 0;border:none;border-top:1px solid #f0f0ef;">', unsafe_allow_html=True)

st.caption("Built with Streamlit · data cached for 15 minutes · not affiliated with Databricks.")
