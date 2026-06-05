import threading
import time
import logging
from typing import Any, Optional
from dataclasses import dataclass
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CacheItem:
    """缓存项"""
    value: Any
    expire_at: float  # 过期时间戳
    created_at: float  # 创建时间戳


class PerItemTTLCache:
    """
    支持 per-item TTL 的缓存
    使用字典存储，惰性清理过期项
    """
    
    def __init__(self, maxsize: int = 1000, default_ttl: int = 300):
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self._data: dict[str, CacheItem] = {}
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
        }
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self._stats["misses"] += 1
                return None
            
            # 检查是否过期
            if time.time() > item.expire_at:
                del self._data[key]
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return item.value
    
    def set(self, key: str, value: Any, ttl: int = None):
        """设置缓存，支持 per-item TTL"""
        with self._lock:
            # 如果达到最大容量，清理过期项
            if len(self._data) >= self.maxsize:
                self._cleanup_expired()
            
            # 如果仍然达到最大容量，删除最旧的项
            if len(self._data) >= self.maxsize:
                self._evict_oldest()
            
            ttl = ttl if ttl is not None else self.default_ttl
            now = time.time()
            self._data[key] = CacheItem(
                value=value,
                expire_at=now + ttl,
                created_at=now,
            )
            self._stats["sets"] += 1
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._stats["deletes"] += 1
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._data.clear()
            logger.info("Cache cleared")
    
    def invalidate_by_prefix(self, prefix: str):
        """清除匹配前缀的缓存"""
        with self._lock:
            keys_to_delete = [k for k in self._data.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._data[key]
                self._stats["deletes"] += 1
            
            if keys_to_delete:
                logger.debug(f"Invalidated {len(keys_to_delete)} cache entries with prefix '{prefix}'")
    
    def _cleanup_expired(self):
        """清理过期项"""
        now = time.time()
        expired_keys = [k for k, v in self._data.items() if now > v.expire_at]
        for key in expired_keys:
            del self._data[key]
            self._stats["evictions"] += 1
    
    def _evict_oldest(self):
        """删除最旧的项"""
        if not self._data:
            return
        oldest_key = min(self._data.keys(), key=lambda k: self._data[k].created_at)
        del self._data[oldest_key]
        self._stats["evictions"] += 1
    
    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
            
            return {
                "size": len(self._data),
                "maxsize": self.maxsize,
                "default_ttl": self.default_ttl,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "sets": self._stats["sets"],
                "deletes": self._stats["deletes"],
                "evictions": self._stats["evictions"],
                "hit_rate": f"{hit_rate:.1%}",
                "total_requests": total_requests,
            }
    
    @property
    def ttl(self) -> int:
        """兼容旧接口"""
        return self.default_ttl


# 全局缓存实例
_cache = PerItemTTLCache(maxsize=settings.CACHE_MAX_SIZE, default_ttl=settings.CACHE_TTL_SECONDS)


def get_cached(key: str) -> Optional[Any]:
    """获取缓存（线程安全）"""
    return _cache.get(key)


def set_cached(key: str, value: Any, ttl: int = None):
    """
    设置缓存（线程安全）
    
    Args:
        key: 缓存键
        value: 缓存值
        ttl: 过期时间（秒），如果不指定则使用全局默认值
    """
    _cache.set(key, value, ttl)


def clear_cache():
    """清空缓存（线程安全）"""
    _cache.clear()


def invalidate_cache(key_prefix: str):
    """清除匹配前缀的缓存（线程安全）"""
    _cache.invalidate_by_prefix(key_prefix)


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    return _cache.get_stats()


def log_cache_stats():
    """记录缓存统计信息"""
    stats = get_cache_stats()
    logger.info(f"缓存统计: 大小={stats['size']}/{stats['maxsize']}, "
                f"命中率={stats['hit_rate']}, "
                f"命中={stats['hits']}, 未命中={stats['misses']}, "
                f"设置={stats['sets']}, 删除={stats['deletes']}, "
                f"淘汰={stats['evictions']}")


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
