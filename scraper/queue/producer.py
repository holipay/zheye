"""
Producer 脚本
抓取 RSS 并发布到 Redis Stream

用法：
    python -m scraper.queue.producer
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scraper.sources.fetcher import Fetcher
from scraper.sources.rss_parser import parse_feed
from scraper.pipeline.classify import classify_hybrid
from scraper.pipeline.dedup import get_link_hash
from scraper.queue.streams import ArticleMessage, StreamProducer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 配置
BATCH_SIZE = 4
BATCH_DELAY_MIN = 20.0
BATCH_DELAY_MAX = 45.0


def load_config() -> dict:
    import yaml
    config_path = Path(__file__).parent.parent / "sources" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def process_source(fetcher: Fetcher, source: dict, producer: StreamProducer) -> int:
    """处理单个 RSS 源，发布到 Stream"""
    name = source["name"]
    url = source["url"]
    lang = source.get("lang", "en")
    category = source.get("category", "其他")
    
    logger.info(f"Fetching {name} from {url}")
    result = await fetcher.fetch(url)
    
    if result["status"] != "ok":
        logger.warning(f"Failed to fetch {name}: {result.get('error', 'unknown')}")
        return 0
    
    feed_items = parse_feed(result["content"], source_name=name, lang=lang, category=category)
    logger.info(f"Parsed {len(feed_items)} items from {name}")
    
    published = 0
    for item in feed_items:
        link_hash = get_link_hash(item.link)
        
        # 混合分类
        article_category, confidence, method = classify_hybrid(
            item.title, item.summary or "", use_llm=True
        )
        if article_category is None:
            logger.debug(f"Filtered out: {item.title}")
            continue
        
        # 创建消息
        article = ArticleMessage(
            title=item.title,
            link=item.link,
            link_hash=link_hash,
            source=name,
            category=article_category,
            lang=lang,
            summary=item.summary or "",
            date=item.date.isoformat() if item.date else "",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # 发布到 Stream
        msg_id = producer.publish(article)
        if msg_id:
            published += 1
    
    return published


async def main():
    """主函数"""
    import random
    
    config = load_config()
    sources = [s for s in config["sources"] if s.get("enabled", True)]
    random.shuffle(sources)
    
    logger.info(f"Starting producer with {len(sources)} sources")
    
    producer = StreamProducer()
    total_published = 0
    
    async with Fetcher(
        timeout=20,
        max_retries=2,
        max_concurrent=BATCH_SIZE,
    ) as fetcher:
        batches = [sources[i:i + BATCH_SIZE] for i in range(0, len(sources), BATCH_SIZE)]
        
        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}")
            
            tasks = [process_source(fetcher, src, producer) for src in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, int):
                    total_published += result
                elif isinstance(result, Exception):
                    logger.error(f"Source error: {result}")
            
            if batch_idx < len(batches) - 1:
                import random
                delay = random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX)
                logger.info(f"Waiting {delay:.1f}s before next batch")
                await asyncio.sleep(delay)
    
    producer.close()
    logger.info(f"Producer finished: published {total_published} articles")


if __name__ == "__main__":
    asyncio.run(main())
