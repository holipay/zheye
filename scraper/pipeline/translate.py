import hashlib
import logging
import os
from typing import Optional
import httpx

from scraper.pipeline.utils import smart_truncate

logger = logging.getLogger(__name__)

MYMEMORY_URL = "https://api.mymemory.translated.net/get"

# 全局 HTTP 客户端（连接池复用）
_http_client: Optional[httpx.AsyncClient] = None

# 内存缓存（避免重复调用 API）
_translation_cache: dict[str, str] = {}
CACHE_MAX_SIZE = 1000


async def get_http_client() -> httpx.AsyncClient:
    """获取或创建 HTTP 客户端（连接池复用）"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30
            )
        )
    return _http_client


async def close_http_client():
    """关闭 HTTP 客户端（应用关闭时调用）"""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


def _get_cache_key(text: str, source_lang: str, target_lang: str) -> str:
    """生成缓存键"""
    return f"{get_text_hash(text)}:{source_lang}:{target_lang}"


def _add_to_cache(key: str, value: str):
    """添加到内存缓存（带大小限制）"""
    global _translation_cache
    if len(_translation_cache) >= CACHE_MAX_SIZE:
        # 删除最旧的一半缓存
        keys_to_remove = list(_translation_cache.keys())[:CACHE_MAX_SIZE // 2]
        for k in keys_to_remove:
            del _translation_cache[k]
    _translation_cache[key] = value


async def translate_text(text: str, source_lang: str = "en", target_lang: str = "zh") -> Optional[str]:
    """
    翻译文本
    
    Args:
        text: 要翻译的文本
        source_lang: 源语言
        target_lang: 目标语言
    
    Returns:
        翻译后的文本，或 None
    """
    if not text or len(text.strip()) == 0:
        return text
    if source_lang == target_lang:
        return text
    
    # 检查内存缓存
    cache_key = _get_cache_key(text, source_lang, target_lang)
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]
    
    try:
        email = os.getenv("MYMEMORY_EMAIL", "user@example.com")
        client = await get_http_client()
        
        # 智能截断：在句子边界截断
        truncated_text = smart_truncate(text, 500, threshold=0.5)
        
        response = await client.get(MYMEMORY_URL, params={
            "q": truncated_text,
            "langpair": f"{source_lang}|{target_lang}",
            "de": email,
        })
        response.raise_for_status()
        data = response.json()
        
        if data.get("responseStatus") == 200:
            translated = data["responseData"]["translatedText"]
            if translated and translated != text:
                # 添加到缓存
                _add_to_cache(cache_key, translated)
                return translated
    except Exception as e:
        logger.error(f"Translation error: {e}")
    
    return None


def get_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
