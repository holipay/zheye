import logging
from typing import Optional
import trafilatura

logger = logging.getLogger(__name__)


def extract_article(url: str, html: Optional[str] = None) -> Optional[str]:
    try:
        if html:
            result = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
        else:
            result = trafilatura.fetch_url(url)
            if result:
                result = trafilatura.extract(result, include_comments=False, include_tables=True)
        return result[:5000] if result else None
    except Exception as e:
        logger.error(f"Error extracting article from {url}: {e}")
        return None
