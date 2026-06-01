import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models.base import async_session
from models.news import News
from models.source_health import SourceHealth
from scraper.pipeline.keywords import match_keywords, sync_keywords_to_db, save_article_keywords, load_keywords
from scraper.pipeline.relations import calculate_and_save_relations

logger = logging.getLogger(__name__)


async def save_news(items: list[dict]) -> int:
    if not items:
        return 0

    keywords_data = load_keywords()
    saved = 0

    async with async_session() as session:
        term_to_id = await sync_keywords_to_db(session, keywords_data)
        await session.commit()

        for item in items:
            try:
                stmt = pg_insert(News).values(**item).on_conflict_do_nothing(index_elements=["link_hash"])
                result = await session.execute(stmt)
                if result.rowcount > 0:
                    saved += 1

                    get_id = select(News.id).where(News.link_hash == item["link_hash"])
                    id_result = await session.execute(get_id)
                    article_id = id_result.scalar_one_or_none()

                    if article_id:
                        matched = match_keywords(
                            title=item.get("title"),
                            translated_title=item.get("translated_title"),
                            summary=item.get("summary"),
                            category=item.get("category", ""),
                            content=item.get("content"),
                        )

                        if matched:
                            await save_article_keywords(session, article_id, matched, term_to_id)
                            await calculate_and_save_relations(session, article_id, item.get("category", ""))

            except Exception as e:
                logger.error(f"Error saving news {item.get('link')}: {e}")

        await session.commit()

    return saved


async def get_existing_hashes(limit: int = 10000) -> set[str]:
    async with async_session() as session:
        result = await session.execute(select(News.link_hash).limit(limit))
        return {row[0] for row in result.fetchall()}


async def get_existing_titles(category: str = None, limit: int = 500) -> list[str]:
    async with async_session() as session:
        query = select(News.title)
        if category:
            query = query.where(News.category == category)
        query = query.order_by(News.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return [row[0] for row in result.fetchall()]


async def update_source_health(source_name: str, success: bool, items_count: int = 0, error: str = None):
    async with async_session() as session:
        result = await session.execute(select(SourceHealth).where(SourceHealth.source_name == source_name))
        health = result.scalar_one_or_none()
        if not health:
            health = SourceHealth(source_name=source_name)
            session.add(health)
        health.total_checks = (health.total_checks or 0) + 1
        health.last_check = datetime.utcnow()
        if success:
            health.total_success = (health.total_success or 0) + 1
            health.consecutive_failures = 0
            health.last_success = datetime.utcnow()
            health.last_items = items_count
        else:
            health.total_failure = (health.total_failure or 0) + 1
            health.consecutive_failures = (health.consecutive_failures or 0) + 1
            health.last_error = error
        if health.total_checks > 0:
            health.success_rate = round((health.total_success or 0) / health.total_checks * 100, 2)
        await session.commit()
