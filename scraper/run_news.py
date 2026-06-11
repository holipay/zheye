import asyncio
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.config import settings
from scraper.sources import Fetcher, parse_feed, extract_article_from_html, extract_date_from_html
from scraper.pipeline import get_link_hash, is_duplicate
from scraper.pipeline.classify import classify_hybrid, detect_article_type
from scraper.pipeline.regions import extract_regions
from scraper.pipeline.dedup import add_to_dedup_cache
from scraper.pipeline.scheduler import filter_and_sort_sources, get_health_summary
from scraper.db import update_source_health, save_news_core, enrich_news, get_existing_hashes, get_existing_titles
from scraper.db.writer import get_source_conditional_headers
from scraper.sources.api_fetcher import MarketDataFetcher
from scraper.monitor import reset_monitor, get_monitor
from models.base import async_session
from models.run_metrics import RunMetrics
from models.market_data import MarketData

# 统一日志配置
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 抓取配置 - 37个源，包括央行/国际组织等敏感站点
BATCH_SIZE = 3                          # 每批处理源数量（减少并发）
BATCH_DELAY_MIN = 30.0                  # 批次间最小延迟（秒）
BATCH_DELAY_MAX = 60.0                  # 批次间最大延迟（秒）
ARTICLE_DELAY_MIN = 3.0                 # 文章间最小延迟
ARTICLE_DELAY_MAX = 7.0                 # 文章间最大延迟

# LLM 分类配置
USE_LLM_CLASSIFIER = settings.USE_LLM_CLASSIFIER

# 共享状态锁
_shared_lock = asyncio.Lock()


def load_config() -> dict:
    config_path = Path(__file__).parent / "sources" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def process_source(fetcher: Fetcher, source: dict, existing_hashes: set, existing_titles: list, extract_content: bool = True) -> list[dict]:
    name = source["name"]
    url = source["url"]
    lang = source.get("lang", "en")
    category = source.get("category", "其他")
    skip_html_fetch = source.get("skip_html_fetch", False)
    items = []

    if skip_html_fetch:
        logger.info(f"{name}: skip_html_fetch enabled, will use RSS summary only")

    headers = await get_source_conditional_headers(name)
    logger.info(f"Fetching {name} from {url}")
    result = await fetcher.fetch(url, etag=headers["etag"], last_modified=headers["last_modified"])

    if result["status"] == "not_modified":
        logger.info(f"{name} not modified (304), skipping")
        await update_source_health(name, success=True, items_count=0)
        return []

    if result["status"] != "ok":
        logger.warning(f"Failed to fetch {name}: {result.get('error', 'unknown')}")
        await update_source_health(name, success=False, error=result.get("error", "fetch failed"))
        return []

    feed_items = parse_feed(result["content"], source_name=name, lang=lang, category=category)
    logger.info(f"Parsed {len(feed_items)} items from {name}")

    for item in feed_items:
        link_hash = get_link_hash(item.link)
        
        # 原子性检查并标记（防止并发任务处理同一篇文章）
        async with _shared_lock:
            if link_hash in existing_hashes:
                continue
            if is_duplicate(item.title, existing_titles):
                continue
            existing_hashes.add(link_hash)
            existing_titles.append(item.title)
            add_to_dedup_cache(item.title)

        content = None
        pub_date = item.date
        if extract_content and not skip_html_fetch:
            html = await fetcher.fetch_html(item.link)
            if html:
                content = extract_article_from_html(item.link, html)
                if content:
                    logger.debug(f"Extracted content from {item.link} ({len(content)} chars)")
                else:
                    logger.debug(f"Content extraction failed for {item.link}, using summary only")
                if not pub_date:
                    pub_date = extract_date_from_html(item.link, html)
                    if pub_date:
                        logger.debug(f"Extracted date from {item.link}: {pub_date}")
            else:
                logger.debug(f"Failed to fetch HTML from {item.link}")
            delay = random.uniform(ARTICLE_DELAY_MIN, ARTICLE_DELAY_MAX)
            await asyncio.sleep(delay)

        if not pub_date:
            logger.warning(f"No publication date for: {item.title} ({item.link})")

        # 混合分类：关键词快速过滤 + LLM 语义分类
        article_category, confidence, method = await classify_hybrid(
            item.title, item.summary or "", use_llm=USE_LLM_CLASSIFIER
        )
        if article_category is None:
            logger.info(f"Filtered out ({method}): {item.title}")
            continue

        article_type = detect_article_type(item.title, item.summary, content)
        regions = extract_regions(item.title, item.summary, content)

        news_item = {
            "title": item.title,
            "translated_title": None,
            "link": item.link,
            "link_hash": link_hash,
            "source": name,
            "category": article_category,
            "lang": lang,
            "summary": item.summary,
            "content": content,
            "article_type": article_type,
            "regions": regions if regions else None,
            "date": pub_date,
        }
        items.append(news_item)

    await update_source_health(
        name,
        success=True,
        items_count=len(items),
        etag=result.get("etag"),
        last_modified=result.get("last_modified"),
    )
    return items


async def fetch_market_data():
    """获取市场数据并保存到数据库（批量插入）"""
    try:
        fetcher = MarketDataFetcher()
        if not fetcher.has_any_api:
            logger.info("No market data API configured, skipping")
            return

        logger.info("Fetching market data...")
        data = await fetcher.fetch_all()

        total_items = sum(len(items) for items in data.values())
        if total_items == 0:
            logger.info("No market data fetched")
            return

        # 收集所有市场数据记录
        all_records = []
        for category, items in data.items():
            for item in items:
                all_records.append({
                    "source": item.source,
                    "data_type": item.data_type,
                    "symbol": item.symbol,
                    "value": item.value,
                    "timestamp": item.timestamp,
                    "extra_data": item.metadata or {},
                })

        # 批量插入
        if all_records:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            async with async_session() as session:
                stmt = pg_insert(MarketData).values(all_records)
                await session.execute(stmt)
                await session.commit()
                logger.info(f"批量插入 {len(all_records)} 条市场数据")

    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")


async def main():
    config = load_config()
    sources = [s for s in config["sources"] if s.get("enabled", True)]
    config_settings = config["settings"]

    # 重置监控器
    reset_monitor()
    monitor = get_monitor()

    # 智能调度：根据健康状态过滤和排序源
    sources = await filter_and_sort_sources(sources)
    
    # 获取健康状态摘要
    health_summary = await get_health_summary()
    logger.info(f"健康状态: {health_summary['healthy_sources']}/{health_summary['total_sources']} 个源可用")

    logger.info(f"Starting news scrape with {len(sources)} sources (batch size: {BATCH_SIZE})")
    start_time = datetime.now(timezone.utc)

    existing_hashes = await get_existing_hashes()
    existing_titles = await get_existing_titles()
    logger.info(f"Found {len(existing_hashes)} existing hashes")

    all_items = []
    sources_attempted = len(sources)
    sources_succeeded = 0
    sources_failed = 0
    items_fetched = 0
    items_deduped = 0

    async with Fetcher(
        timeout=config_settings.get("fetch_timeout", 20),
        max_retries=config_settings.get("max_retries", 2),
        max_concurrent=BATCH_SIZE,
    ) as fetcher:
        batches = [sources[i:i + BATCH_SIZE] for i in range(0, len(sources), BATCH_SIZE)]

        failed_sources = []
        
        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} sources)")

            tasks = [process_source(fetcher, src, existing_hashes, existing_titles) for src in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Source processing error: {result}")
                    sources_failed += 1
                    failed_sources.append(batch[i])
                    monitor.record_source_result(batch[i]["name"], False, error=str(result))
                elif isinstance(result, list):
                    all_items.extend(result)
                    if len(result) > 0:
                        sources_succeeded += 1
                        monitor.record_source_result(batch[i]["name"], True, items_count=len(result))

            if batch_idx < len(batches) - 1:
                delay = random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX)
                logger.info(f"Waiting {delay:.1f}s before next batch")
                await asyncio.sleep(delay)
        
        # 重试失败的源（最多重试1次）
        if failed_sources:
            logger.info(f"重试 {len(failed_sources)} 个失败源...")
            retry_delay = random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX)
            await asyncio.sleep(retry_delay)
            
            for src in failed_sources:
                try:
                    result = await process_source(fetcher, src, existing_hashes, existing_titles)
                    if isinstance(result, list):
                        all_items.extend(result)
                        if len(result) > 0:
                            sources_succeeded += 1
                            sources_failed -= 1
                            monitor.record_source_result(src["name"], True, items_count=len(result))
                            logger.info(f"重试成功: {src['name']}")
                except Exception as e:
                    logger.error(f"重试失败 {src['name']}: {e}")
                    monitor.record_source_result(src["name"], False, error=str(e))

    items_fetched = len(all_items)
    items_final = 0

    if all_items:
        # Phase 1: 原子插入新闻（核心数据，必须成功）
        saved, hash_to_id = await save_news_core(all_items)
        items_final = saved
        items_deduped = items_fetched - saved
        monitor.record_save_result(saved)
        logger.info(f"Phase 1: {saved} 篇新闻已入库")

        # Phase 2: 独立富化（best effort，失败不影响新闻数据）
        if hash_to_id:
            enrich_stats = await enrich_news(hash_to_id, all_items)
            logger.info(
                f"Phase 2: 关键词={enrich_stats['keywords']}, "
                f"实体={enrich_stats['entities']}, "
                f"事件={enrich_stats['events']}, "
                f"关系={enrich_stats['relations']}"
            )
    else:
        logger.info("No new items to save")

    # 获取市场数据
    await fetch_market_data()

    # 记录运行摘要
    monitor.check_alerts()
    monitor.log_summary()

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Scrape completed in {duration:.1f}s")

    try:
        async with async_session() as session:
            metrics = RunMetrics(
                run_type="news_scrape",
                started_at=start_time,
                finished_at=datetime.now(timezone.utc),
                duration_seconds=int(duration),
                sources_attempted=sources_attempted,
                sources_succeeded=sources_succeeded,
                sources_failed=sources_failed,
                items_fetched=items_fetched,
                items_deduped=items_deduped,
                items_final=items_final,
            )
            session.add(metrics)
            await session.commit()
            logger.info("Run metrics saved")
    except Exception as e:
        logger.error(f"Failed to save run metrics: {e}")


if __name__ == "__main__":
    asyncio.run(main())
