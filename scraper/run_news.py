import asyncio
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scraper.sources.fetcher import Fetcher
from scraper.sources.rss_parser import parse_feed
from scraper.sources.article_extractor import extract_article_from_html
from scraper.pipeline.dedup import get_link_hash, is_duplicate
from scraper.pipeline.classify import classify_by_keywords
from scraper.db.writer import save_news, get_existing_hashes, get_existing_titles, update_source_health, get_source_conditional_headers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 5
BATCH_DELAY_MIN = 15.0
BATCH_DELAY_MAX = 40.0
ARTICLE_DELAY_MIN = 2.0
ARTICLE_DELAY_MAX = 5.0


def load_config() -> dict:
    config_path = Path(__file__).parent / "sources" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def process_source(fetcher: Fetcher, source: dict, existing_hashes: set, existing_titles: list, extract_content: bool = True) -> list[dict]:
    name = source["name"]
    url = source["url"]
    lang = source.get("lang", "en")
    category = source.get("category", "其他")
    items = []

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
        if link_hash in existing_hashes:
            continue
        if is_duplicate(item.title, existing_titles):
            continue

        content = None
        if extract_content:
            html = await fetcher.fetch_html(item.link)
            if html:
                content = extract_article_from_html(item.link, html)
                if content:
                    logger.debug(f"Extracted content from {item.link} ({len(content)} chars)")
                else:
                    logger.debug(f"Content extraction failed for {item.link}, using summary only")
            else:
                logger.debug(f"Failed to fetch HTML from {item.link}")
            delay = random.uniform(ARTICLE_DELAY_MIN, ARTICLE_DELAY_MAX)
            await asyncio.sleep(delay)

        news_item = {
            "title": item.title,
            "translated_title": None,
            "link": item.link,
            "link_hash": link_hash,
            "source": name,
            "category": category,
            "lang": lang,
            "summary": item.summary,
            "content": content,
            "date": item.date,
        }
        items.append(news_item)
        existing_hashes.add(link_hash)
        existing_titles.append(item.title)

    await update_source_health(
        name,
        success=True,
        items_count=len(items),
        etag=result.get("etag"),
        last_modified=result.get("last_modified"),
    )
    return items


async def main():
    config = load_config()
    sources = config["sources"]
    settings = config["settings"]

    random.shuffle(sources)

    logger.info(f"Starting news scrape with {len(sources)} sources (batch size: {BATCH_SIZE})")
    start_time = datetime.utcnow()

    existing_hashes = await get_existing_hashes()
    existing_titles = await get_existing_titles()
    logger.info(f"Found {len(existing_hashes)} existing hashes")

    all_items = []
    async with Fetcher(
        timeout=settings.get("fetch_timeout", 20),
        max_retries=settings.get("max_retries", 2),
        max_concurrent=BATCH_SIZE,
    ) as fetcher:
        batches = [sources[i:i + BATCH_SIZE] for i in range(0, len(sources), BATCH_SIZE)]

        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} sources)")

            tasks = [process_source(fetcher, src, existing_hashes, existing_titles) for src in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Source processing error: {result}")
                elif isinstance(result, list):
                    all_items.extend(result)

            if batch_idx < len(batches) - 1:
                delay = random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX)
                logger.info(f"Waiting {delay:.1f}s before next batch")
                await asyncio.sleep(delay)

    if all_items:
        saved = await save_news(all_items)
        logger.info(f"Saved {saved} new items to database")
    else:
        logger.info("No new items to save")

    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"Scrape completed in {duration:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
