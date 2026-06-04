import logging
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import feedparser

logger = logging.getLogger(__name__)

# HTML 标签清理正则
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_HTML_ENTITY_RE = re.compile(r'&(?:nbsp|amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);')

# HTML 实体映射
_HTML_ENTITY_MAP = {
    '&nbsp;': ' ', '&quot;': '"', '&apos;': "'",
    '&amp;': '&', '&lt;': '<', '&gt;': '>',
}


def strip_html(text: str) -> str:
    """清理 HTML 标签和实体"""
    if not text:
        return text
    # 先清理 HTML 标签（在实体替换之前，避免 < > 被误删）
    text = _HTML_TAG_RE.sub('', text)
    # 再替换 HTML 实体为正确字符
    for entity, char in _HTML_ENTITY_MAP.items():
        text = text.replace(entity, char)
    # 替换剩余的 HTML 实体（数字实体等）
    text = _HTML_ENTITY_RE.sub(' ', text)
    return re.sub(r'\s+', ' ', text).strip()


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
                summary = strip_html(summary)[:1000]
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
