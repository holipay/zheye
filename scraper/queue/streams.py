"""
Redis Streams 消息队列模块
实现生产者-消费者模式，解耦抓取和处理

架构：
  Producer (抓取RSS) → Redis Stream → Consumer (处理入库)

优势：
1. 抓取和处理解耦，可独立扩展
2. 消息持久化，支持重试
3. 支持消费者组，可水平扩展
4. 轻量级，无额外依赖
"""

import json
import logging
import os
import time
from typing import Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Redis 配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_NAME = os.getenv("REDIS_STREAM_NAME", "zheye:articles")
CONSUMER_GROUP = os.getenv("REDIS_CONSUMER_GROUP", "zheye:workers")
CONSUMER_NAME = os.getenv("REDIS_CONSUMER_NAME", f"worker-{os.getpid()}")

# Redis 客户端缓存
_redis_client = None


def _get_redis():
    """获取 Redis 客户端（懒加载）"""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()
            logger.info(f"Connected to Redis: {REDIS_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            _redis_client = None
    return _redis_client


@dataclass
class ArticleMessage:
    """文章消息格式"""
    title: str
    link: str
    link_hash: str
    source: str
    category: str
    lang: str
    summary: str = ""
    content: str = ""
    date: str = ""
    fetched_at: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ArticleMessage':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class StreamProducer:
    """
    Redis Streams 生产者
    
    将抓取的文章发布到 Redis Stream
    """
    
    def __init__(self, stream_name: str = None):
        self.stream_name = stream_name or STREAM_NAME
        self._redis = None
    
    @property
    def redis(self):
        if self._redis is None:
            self._redis = _get_redis()
        return self._redis
    
    def publish(self, article: ArticleMessage) -> Optional[str]:
        """
        发布文章到 Stream
        
        Args:
            article: 文章消息
            
        Returns:
            消息ID，失败返回None
        """
        if not self.redis:
            logger.error("Redis not connected")
            return None
        
        try:
            msg_id = self.redis.xadd(
                self.stream_name,
                article.to_dict(),
                maxlen=10000,  # 保留最近10000条消息
            )
            logger.debug(f"Published article: {article.title[:50]}... -> {msg_id}")
            return msg_id
        except Exception as e:
            logger.error(f"Failed to publish article: {e}")
            return None
    
    def publish_batch(self, articles: list[ArticleMessage]) -> int:
        """
        批量发布文章
        
        Args:
            articles: 文章列表
            
        Returns:
            成功发布的数量
        """
        if not self.redis:
            logger.error("Redis not connected")
            return 0
        
        count = 0
        pipe = self.redis.pipeline()
        
        for article in articles:
            try:
                pipe.xadd(
                    self.stream_name,
                    article.to_dict(),
                    maxlen=10000,
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to queue article: {e}")
        
        try:
            pipe.execute()
            logger.info(f"Published {count} articles to stream")
        except Exception as e:
            logger.error(f"Failed to execute pipeline: {e}")
            count = 0
        
        return count
    
    def close(self):
        """关闭连接"""
        if self._redis:
            self._redis.close()
            self._redis = None


class StreamConsumer:
    """
    Redis Streams 消费者
    
    从 Redis Stream 消费文章并处理
    """
    
    def __init__(self, stream_name: str = None, group_name: str = None, consumer_name: str = None):
        self.stream_name = stream_name or STREAM_NAME
        self.group_name = group_name or CONSUMER_GROUP
        self.consumer_name = consumer_name or CONSUMER_NAME
        self._redis = None
        self._running = False
    
    @property
    def redis(self):
        if self._redis is None:
            self._redis = _get_redis()
        return self._redis
    
    def _ensure_group(self):
        """确保消费者组存在"""
        if not self.redis:
            return False
        
        try:
            # 创建消费者组（如果不存在）
            self.redis.xgroup_create(
                self.stream_name,
                self.group_name,
                id='0',
                mkstream=True
            )
            logger.info(f"Created consumer group: {self.group_name}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer group already exists: {self.group_name}")
            else:
                logger.error(f"Failed to create consumer group: {e}")
                return False
        
        return True
    
    def consume(self, handler, block_ms: int = 5000, count: int = 10):
        """
        消费消息
        
        Args:
            handler: 消息处理函数，接收 ArticleMessage 参数
            block_ms: 阻塞等待时间（毫秒）
            count: 每次拉取的消息数量
        """
        if not self._ensure_group():
            logger.error("Failed to ensure consumer group")
            return
        
        self._running = True
        logger.info(f"Consumer started: {self.consumer_name} @ {self.group_name}")
        
        while self._running:
            try:
                # 读取消息
                messages = self.redis.xreadgroup(
                    self.group_name,
                    self.consumer_name,
                    {self.stream_name: '>'},
                    count=count,
                    block=block_ms
                )
                
                if not messages:
                    continue
                
                # 处理消息
                for stream, entries in messages:
                    for msg_id, data in entries:
                        try:
                            # 转换为 ArticleMessage
                            article = ArticleMessage.from_dict(data)
                            
                            # 调用处理函数
                            handler(article)
                            
                            # 确认消息处理完成
                            self.redis.xack(
                                self.stream_name,
                                self.group_name,
                                msg_id
                            )
                            logger.debug(f"Processed message: {msg_id}")
                            
                        except Exception as e:
                            logger.error(f"Failed to process message {msg_id}: {e}")
                            # 消息未确认，会被重新投递
                
            except Exception as e:
                if self._running:
                    logger.error(f"Consumer error: {e}")
                    time.sleep(1)  # 避免快速循环
    
    def stop(self):
        """停止消费"""
        self._running = False
        logger.info(f"Consumer stopped: {self.consumer_name}")
    
    def close(self):
        """关闭连接"""
        if self._redis:
            self._redis.close()
            self._redis = None
    
    def get_pending(self) -> list[dict]:
        """获取未确认的消息"""
        if not self.redis:
            return []
        
        try:
            pending = self.redis.xpending_range(
                self.stream_name,
                self.group_name,
                min='-',
                max='+',
                count=100
            )
            return pending
        except Exception as e:
            logger.error(f"Failed to get pending messages: {e}")
            return []
    
    def get_stream_info(self) -> dict:
        """获取 Stream 信息"""
        if not self.redis:
            return {}
        
        try:
            info = self.redis.xinfo_stream(self.stream_name)
            return {
                'length': info.get('length', 0),
                'first_entry': info.get('first-entry'),
                'last_entry': info.get('last-entry'),
            }
        except Exception as e:
            logger.error(f"Failed to get stream info: {e}")
            return {}


def get_stream_length() -> int:
    """获取 Stream 长度"""
    redis = _get_redis()
    if not redis:
        return 0
    
    try:
        return redis.xlen(STREAM_NAME)
    except Exception as e:
        logger.error(f"Failed to get stream length: {e}")
        return 0


def clear_stream():
    """清空 Stream"""
    redis = _get_redis()
    if not redis:
        return
    
    try:
        redis.xtrim(STREAM_NAME, maxlen=0)
        logger.info(f"Cleared stream: {STREAM_NAME}")
    except Exception as e:
        logger.error(f"Failed to clear stream: {e}")
