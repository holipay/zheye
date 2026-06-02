import time
from typing import Any, Optional
from cachetools import TTLCache
from app.config import settings

_cache = TTLCache(maxsize=100, ttl=settings.CACHE_TTL_SECONDS)


def get_cached(key: str) -> Optional[Any]:
    return _cache.get(key)


def set_cached(key: str, value: Any, ttl: int = None):
    if ttl:
        cache = TTLCache(maxsize=1, ttl=ttl)
        cache[key] = value
        _cache[key] = cache[key]
    else:
        _cache[key] = value


def clear_cache():
    _cache.clear()
