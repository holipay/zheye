import logging
import re
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


async def extract_article_async(url: str, client) -> Optional[str]:
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        html = response.text

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
