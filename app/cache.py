import time
import threading
from typing import Any, Optional
from cachetools import TTLCache
from app.config import settings

# 线程锁
_lock = threading.RLock()

# 使用线程安全的缓存
_cache = TTLCache(maxsize=100, ttl=settings.CACHE_TTL_SECONDS)


def get_cached(key: str) -> Optional[Any]:
    """获取缓存（线程安全）"""
    with _lock:
        return _cache.get(key)


def set_cached(key: str, value: Any, ttl: int = None):
    """设置缓存（线程安全）"""
    with _lock:
        if ttl:
            # 使用 cachetools 的 TTLCache 来处理自定义 TTL
            # 创建临时缓存来计算过期时间
            temp_cache = TTLCache(maxsize=1, ttl=ttl)
            temp_cache[key] = value
            _cache[key] = temp_cache[key]
        else:
            _cache[key] = value


def clear_cache():
    """清空缓存（线程安全）"""
    with _lock:
        _cache.clear()


def invalidate_cache(key_prefix: str):
    """清除匹配前缀的缓存（线程安全）"""
    with _lock:
        keys_to_delete = [k for k in _cache.keys() if k.startswith(key_prefix)]
        for key in keys_to_delete:
            del _cache[key]


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    with _lock:
        return {
            "size": len(_cache),
            "maxsize": _cache.maxsize,
            "ttl": _cache.ttl,
            "hits": _cache.hits if hasattr(_cache, 'hits') else 0,
            "misses": _cache.misses if hasattr(_cache, 'misses') else 0,
        }
