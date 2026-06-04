import threading
import logging
from typing import Any, Optional
from cachetools import TTLCache
from app.config import settings

logger = logging.getLogger(__name__)

# 线程锁
_lock = threading.RLock()

# 使用线程安全的缓存
_cache = TTLCache(maxsize=settings.CACHE_MAX_SIZE, ttl=settings.CACHE_TTL_SECONDS)

# 缓存统计
_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "deletes": 0,
}


def get_cached(key: str) -> Optional[Any]:
    """获取缓存（线程安全）"""
    with _lock:
        value = _cache.get(key)
        if value is not None:
            _stats["hits"] += 1
        else:
            _stats["misses"] += 1
        return value


def set_cached(key: str, value: Any, ttl: int = None):
    """
    设置缓存（线程安全）
    
    注意：cachetools.TTLCache 不支持 per-item TTL，
    自定义 ttl 参数当前会被忽略，使用全局 TTL。
    如需 per-item TTL，可考虑使用 Redis 或其他缓存方案。
    """
    with _lock:
        _cache[key] = value
        _stats["sets"] += 1


def clear_cache():
    """清空缓存（线程安全）"""
    with _lock:
        _cache.clear()
        logger.info("Cache cleared")


def invalidate_cache(key_prefix: str):
    """清除匹配前缀的缓存（线程安全）"""
    with _lock:
        keys_to_delete = [k for k in _cache.keys() if k.startswith(key_prefix)]
        for key in keys_to_delete:
            del _cache[key]
            _stats["deletes"] += 1
        
        if keys_to_delete:
            logger.debug(f"Invalidated {len(keys_to_delete)} cache entries with prefix '{key_prefix}'")


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    with _lock:
        total_requests = _stats["hits"] + _stats["misses"]
        hit_rate = _stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(_cache),
            "maxsize": _cache.maxsize,
            "ttl": _cache.ttl,
            "hits": _stats["hits"],
            "misses": _stats["misses"],
            "sets": _stats["sets"],
            "deletes": _stats["deletes"],
            "hit_rate": f"{hit_rate:.1%}",
            "total_requests": total_requests,
        }


def log_cache_stats():
    """记录缓存统计信息"""
    stats = get_cache_stats()
    logger.info(f"缓存统计: 大小={stats['size']}/{stats['maxsize']}, "
                f"命中率={stats['hit_rate']}, "
                f"命中={stats['hits']}, 未命中={stats['misses']}, "
                f"设置={stats['sets']}, 删除={stats['deletes']}")


def warmup_cache(warmup_func, *args, **kwargs):
    """
    缓存预热
    
    Args:
        warmup_func: 预热函数，返回 (key, value) 元组列表
        *args, **kwargs: 传递给预热函数的参数
    """
    try:
        items = warmup_func(*args, **kwargs)
        if items:
            for key, value in items:
                set_cached(key, value)
            logger.info(f"Cache warmed up with {len(items)} items")
    except Exception as e:
        logger.warning(f"Cache warmup failed: {e}")
