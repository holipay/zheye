"""
消息队列模块
使用 Redis Streams 实现生产者-消费者模式
"""

from scraper.queue.streams import (
    ArticleMessage,
    StreamProducer,
    StreamConsumer,
    get_stream_length,
    clear_stream,
)

__all__ = [
    'ArticleMessage',
    'StreamProducer',
    'StreamConsumer',
    'get_stream_length',
    'clear_stream',
]
