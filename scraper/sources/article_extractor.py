import logging
import re
from datetime import datetime
from typing import Optional
import trafilatura

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 5000


def _clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_article(url: str, html: Optional[str] = None) -> Optional[str]:
    try:
        if html:
            result = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
        else:
            result = trafilatura.fetch_url(url)
            if result:
                result = trafilatura.extract(result, include_comments=False, include_tables=True)
        if result:
            result = _clean_text(result)
            return result[:MAX_CONTENT_LENGTH] if result else None
        return None
    except Exception as e:
        logger.error(f"Error extracting article from {url}: {e}")
        return None


def extract_article_from_html(url: str, html: str) -> Optional[str]:
    try:
        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            output_format='txt',
        )
        if result:
            result = _clean_text(result)
            return result[:MAX_CONTENT_LENGTH] if result else None
        return None
    except Exception as e:
        logger.warning(f"Failed to extract article from {url}: {e}")
        return None


def extract_date_from_html(url: str, html: str) -> Optional[datetime]:
    try:
        metadata = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            output_format='json',
        )
        if metadata:
            import json
            data = json.loads(metadata)
            date_str = data.get("date")
            if date_str:
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass
        return None
    except Exception as e:
        logger.debug(f"Failed to extract date from {url}: {e}")
        return None
