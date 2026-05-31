import asyncio
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 2
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class Fetcher:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def fetch(self, url: str, etag: Optional[str] = None, last_modified: Optional[str] = None) -> dict:
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.get(url, headers=headers)
                if response.status_code == 304:
                    return {"status": "not_modified", "url": url}
                response.raise_for_status()
                return {
                    "status": "ok",
                    "url": url,
                    "content": response.text,
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "status_code": response.status_code,
                }
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} for {url} (attempt {attempt + 1})")
                if attempt == self.max_retries:
                    return {"status": "error", "url": url, "error": str(e), "status_code": e.response.status_code}
            except httpx.RequestError as e:
                logger.warning(f"Request error for {url}: {e} (attempt {attempt + 1})")
                if attempt == self.max_retries:
                    return {"status": "error", "url": url, "error": str(e)}
            await asyncio.sleep(1)
        return {"status": "error", "url": url, "error": "Max retries exceeded"}


async def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_RETRIES) -> dict:
    async with Fetcher(timeout=timeout, max_retries=max_retries) as fetcher:
        return await fetcher.fetch(url)
