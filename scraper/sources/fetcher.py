import asyncio
import ipaddress
import logging
import random
from typing import Optional
from urllib.parse import urlparse
import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

MIN_DELAY = 1.5
MAX_DELAY = 4.0
DOMAIN_MIN_DELAY = 6.0
DOMAIN_MAX_DELAY = 15.0


def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


def get_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.hostname or url


def _is_private_ip(hostname: str) -> bool:
    """检查是否为内网IP地址"""
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        # 不是IP地址，检查常见内网主机名
        return hostname in ("localhost", "metadata.google.internal", "169.254.169.254")


def validate_url(url: str) -> bool:
    """
    验证URL是否安全（SSRF防护）
    
    拒绝：
    - 非HTTP/HTTPS协议
    - 内网IP地址（127.0.0.1, 10.x.x.x, 172.16-31.x.x, 192.168.x.x, 169.254.x.x）
    - localhost
    - 元数据服务地址
    """
    try:
        parsed = urlparse(url)
        
        # 只允许HTTP和HTTPS协议
        if parsed.scheme not in ("http", "https"):
            logger.warning(f"SSRF防护: 拒绝非HTTP协议 {parsed.scheme}")
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # 检查是否为内网地址
        if _is_private_ip(hostname):
            logger.warning(f"SSRF防护: 拒绝内网地址 {hostname}")
            return False
        
        return True
    except Exception:
        return False


class Fetcher:
    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_RETRIES,
        max_concurrent: int = 5,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._domain_last_request: dict[str, float] = {}

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": get_random_ua()},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def _wait_domain_delay(self, url: str):
        domain = get_domain(url)
        now = asyncio.get_event_loop().time()
        last = self._domain_last_request.get(domain, 0)
        elapsed = now - last
        delay = random.uniform(DOMAIN_MIN_DELAY, DOMAIN_MAX_DELAY)

        if elapsed < delay:
            wait = delay - elapsed
            logger.debug(f"Domain {domain} rate limit, waiting {wait:.1f}s")
            await asyncio.sleep(wait)

        self._domain_last_request[domain] = asyncio.get_event_loop().time()

    async def fetch(self, url: str, etag: Optional[str] = None, last_modified: Optional[str] = None) -> dict:
        # SSRF防护：验证URL
        if not validate_url(url):
            return {"status": "error", "url": url, "error": "URL validation failed (SSRF protection)"}
        
        headers = {"User-Agent": get_random_ua()}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        async with self._semaphore:
            await self._wait_domain_delay(url)

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
                    if e.response.status_code == 429:
                        retry_after = int(e.response.headers.get("Retry-After", 30))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                    elif attempt == self.max_retries:
                        return {"status": "error", "url": url, "error": str(e), "status_code": e.response.status_code}
                except httpx.RequestError as e:
                    logger.warning(f"Request error for {url}: {e} (attempt {attempt + 1})")
                    if attempt == self.max_retries:
                        return {"status": "error", "url": url, "error": str(e)}

                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                await asyncio.sleep(delay)

        return {"status": "error", "url": url, "error": "Max retries exceeded"}


    async def fetch_html(self, url: str) -> Optional[str]:
        result = await self.fetch(url)
        if result["status"] == "ok":
            return result["content"]
        return None


async def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_RETRIES) -> dict:
    async with Fetcher(timeout=timeout, max_retries=max_retries) as fetcher:
        return await fetcher.fetch(url)
