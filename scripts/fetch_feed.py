"""
Fetch the Databricks docs release-notes RSS feed and normalize it into a
simple list of dicts that both the Streamlit app and the static (GitHub
Pages) site can consume.

Usage:
    python scripts/fetch_feed.py                 # writes docs/data.json
    python scripts/fetch_feed.py --out path.json  # custom output path
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import requests

FEED_URL = "https://docs.databricks.com/aws/en/feed.xml"
USER_AGENT = "databricks-hn-reader/1.0 (+https://github.com/)"

# Rough category guess from the URL path, so the UI can offer a filter
# similar to HN's sub-sections, without needing anything the feed doesn't
# already give us.
_CATEGORY_HINTS = [
    ("ai-bi", "AI/BI"),
    ("lakebase", "Lakebase"),
    ("lakeflow", "Lakeflow"),
    ("unity-catalog", "Unity Catalog"),
    ("machine-learning", "Machine Learning"),
    ("generative-ai", "Generative AI"),
    ("sql", "SQL"),
    ("security", "Security"),
    ("release-notes/product", "Platform"),
]


def _guess_category(link: str) -> str:
    path = urlparse(link).path.lower()
    for needle, label in _CATEGORY_HINTS:
        if needle in path:
            return label
    return "General"


def _strip_html(raw: str) -> str:
    """Turn the (HTML) <description> into short, clean plain text."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(entry) -> str:
    """Return an ISO-8601 UTC timestamp string, best-effort."""
    for key in ("published", "updated"):
        val = getattr(entry, key, None)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def fetch_items(feed_url: str = FEED_URL, timeout: int = 20) -> list[dict]:
    resp = requests.get(feed_url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)

    items = []
    for entry in parsed.entries:
        link = getattr(entry, "link", "") or ""
        title = getattr(entry, "title", "(untitled)") or "(untitled)"
        guid = getattr(entry, "id", None) or link
        summary_raw = getattr(entry, "summary", "") or ""
        summary = _strip_html(summary_raw)
        published_iso = _parse_date(entry)
        item_id = hashlib.sha1(guid.encode("utf-8")).hexdigest()[:12]

        items.append(
            {
                "id": item_id,
                "title": html.unescape(title).strip(),
                "link": link,
                "summary": summary[:600],
                "published": published_iso,
                "category": _guess_category(link),
                "domain": urlparse(link).netloc or "docs.databricks.com",
            }
        )

    # Newest first.
    items.sort(key=lambda x: x["published"], reverse=True)
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="docs/data.json",
        help="Output path for the generated JSON (default: docs/data.json)",
    )
    parser.add_argument("--feed-url", default=FEED_URL)
    args = parser.parse_args()

    try:
        items = fetch_items(args.feed_url)
    except Exception as exc:  # pragma: no cover
        print(f"Failed to fetch/parse feed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": args.feed_url,
        "count": len(items),
        "items": items,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(items)} items to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
