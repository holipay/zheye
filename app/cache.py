import threading
from typing import Any, Optional
from cachetools import TTLCache
from app.config import settings

# 线程锁
_lock = threading.RLock()

# 使用线程安全的缓存
_cache = TTLCache(maxsize=settings.CACHE_MAX_SIZE, ttl=settings.CACHE_TTL_SECONDS)


def get_cached(key: str) -> Optional[Any]:
    """获取缓存（线程安全）"""
    with _lock:
        return _cache.get(key)


def set_cached(key: str, value: Any, ttl: int = None):
    """
    设置缓存（线程安全）
    
    注意：cachetools.TTLCache 不支持 per-item TTL，
    自定义 ttl 参数当前会被忽略，使用全局 TTL。
    如需 per-item TTL，可考虑使用 Redis 或其他缓存方案。
    """
    with _lock:
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
