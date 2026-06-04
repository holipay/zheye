"""
Consumer 脚本
从 Redis Stream 消费文章并处理入库

用法：
    python -m scraper.queue.consumer
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scraper.queue.streams import ArticleMessage, StreamConsumer
from scraper.db.writer import save_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def process_article(article: ArticleMessage):
    """
    处理单篇文章
    
    Args:
        article: 文章消息
    """
    # 转换为 save_news 格式
    item = {
        "title": article.title,
        "translated_title": None,
        "link": article.link,
        "link_hash": article.link_hash,
        "source": article.source,
        "category": article.category,
        "lang": article.lang,
        "summary": article.summary,
        "content": article.content,
        "article_type": "news",
        "regions": None,
        "date": article.date if article.date else None,
    }
    
    # 保存到数据库
    try:
        import asyncio
        saved = asyncio.run(save_news([item]))
        if saved > 0:
            logger.info(f"Saved article: {article.title[:50]}...")
        else:
            logger.debug(f"Article already exists: {article.title[:50]}...")
    except Exception as e:
        logger.error(f"Failed to save article: {e}")
        raise  # 重新抛出异常，让消息未确认


def main():
    """主函数"""
    logger.info("Starting consumer...")
    
    consumer = StreamConsumer()
    
    try:
        # 开始消费
        consumer.consume(
            handler=process_article,
            block_ms=5000,
            count=10,
        )
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    finally:
        consumer.stop()
        consumer.close()
        logger.info("Consumer stopped")


if __name__ == "__main__":
    main()
