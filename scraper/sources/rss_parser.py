import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import feedparser

logger = logging.getLogger(__name__)


@dataclass
class RSSItem:
    title: str
    link: str
    summary: Optional[str] = None
    date: Optional[datetime] = None
    lang: str = "en"
    source: str = ""
    category: str = ""


def parse_date(entry) -> Optional[datetime]:
    for field in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except Exception:
                continue
    return None


def parse_feed(content: str, source_name: str = "", lang: str = "en", category: str = "") -> list[RSSItem]:
    items = []
    try:
        feed = feedparser.parse(content)
        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue
            summary = getattr(entry, "summary", None)
            if summary:
                summary = summary.strip()[:1000]
            date = parse_date(entry)
            items.append(RSSItem(
                title=title,
                link=link,
                summary=summary,
                date=date,
                lang=lang,
                source=source_name,
                category=category,
            ))
    except Exception as e:
        logger.error(f"Error parsing feed: {e}")
    return items
