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


def invalidate_cache(key_prefix: str):
    """清除匹配前缀的缓存"""
    keys_to_delete = [k for k in _cache.keys() if k.startswith(key_prefix)]
    for key in keys_to_delete:
        del _cache[key]
