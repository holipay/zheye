import logging
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models.base import async_session
from models.news import News
from models.event import Event
from models.source_health import SourceHealth
from scraper.pipeline.keywords import match_keywords, sync_keywords_to_db, save_article_keywords, load_keywords
from scraper.pipeline.entities import extract_entities, sync_entities_to_db, save_article_entities
from scraper.pipeline.relations import calculate_and_save_relations
from scraper.pipeline.events import detect_event_from_article, update_event_with_article
from app.cache import invalidate_cache

logger = logging.getLogger(__name__)


async def save_news(items: list[dict[str, any]]) -> int:
    if not items:
        return 0

    keywords_data = load_keywords()
    saved = 0
    events_saved = 0
    entity_records_to_insert = []

    async with async_session() as session:
        term_to_id = await sync_keywords_to_db(session, keywords_data)
        await session.commit()

        # ========== 阶段1: 批量插入新闻 ==========
        stmt = (
            pg_insert(News)
            .values(items)
            .on_conflict_do_nothing(index_elements=["link_hash"])
            .returning(News.id, News.link_hash)
        )
        result = await session.execute(stmt)
        inserted_rows = result.fetchall()
        saved = len(inserted_rows)

        if saved == 0:
            logger.info("No new articles to insert")
            return 0

        # 构建 link_hash -> article_id 映射
        hash_to_id = {row[1]: row[0] for row in inserted_rows}
        # 构建 link_hash -> item 映射（用于后处理）
        hash_to_item = {item["link_hash"]: item for item in items if "link_hash" in item}

        # ========== 阶段2: 批量后处理关键词/实体/事件 ==========
        all_keyword_records = []
        all_entity_records = []
        all_entities = []  # 收集所有实体，用于批量同步

        for link_hash, article_id in hash_to_id.items():
            item = hash_to_item.get(link_hash)
            if not item:
                continue

            # 关键词匹配（CPU 密集，但不涉及 IO）
            try:
                matched = match_keywords(
                    title=item.get("title"),
                    translated_title=item.get("translated_title"),
                    summary=item.get("summary"),
                    category=item.get("category", ""),
                    content=item.get("content"),
                )
                if matched:
                    for mk in matched:
                        keyword_id = term_to_id.get(mk["term"])
                        if keyword_id:
                            all_keyword_records.append({
                                "article_id": article_id,
                                "keyword_id": keyword_id,
                                "relevance": mk.get("relevance", 1.0),
                            })
            except Exception as e:
                logger.warning(f"关键词匹配失败 (article_id={article_id}): {e}")

            # 实体提取（CPU 密集，但不涉及 IO）
            try:
                entities = extract_entities(
                    title=item.get("title", ""),
                    summary=item.get("summary", ""),
                    content=item.get("content"),
                )
                if entities:
                    all_entities.append((article_id, entities))
            except Exception as e:
                logger.warning(f"实体提取失败 (article_id={article_id}): {e}")

            # 事件检测
            try:
                event_result = await process_article_event(session, item)
                if event_result:
                    events_saved += 1
            except Exception as e:
                logger.warning(f"事件检测失败 (article_id={article_id}): {e}")

        # ========== 阶段3: 批量插入关键词关联 ==========
        if all_keyword_records:
            try:
                from models.article_keyword import ArticleKeyword
                kw_stmt = (
                    pg_insert(ArticleKeyword)
                    .values(all_keyword_records)
                    .on_conflict_do_nothing()
                )
                await session.execute(kw_stmt)
                logger.debug(f"批量插入 {len(all_keyword_records)} 条关键词关联")
            except Exception as e:
                logger.warning(f"批量插入关键词关联失败: {e}")

        # 批量计算文章关系
        for link_hash, article_id in hash_to_id.items():
            item = hash_to_item.get(link_hash)
            if item:
                try:
                    await calculate_and_save_relations(session, article_id, item.get("category", ""))
                except Exception as e:
                    logger.warning(f"关系计算失败 (article_id={article_id}): {e}")

        # ========== 阶段4: 批量同步实体并收集关联记录 ==========
        entity_records_to_insert = []
        if all_entities:
            try:
                # 合并所有实体，一次性同步到数据库
                merged_entities = {}
                for article_id, entities in all_entities:
                    for ent in entities:
                        name = ent["name"]
                        if name not in merged_entities:
                            merged_entities[name] = ent

                entity_name_to_id = await sync_entities_to_db(session, list(merged_entities.values()))

                # 构建实体关联记录
                for article_id, entities in all_entities:
                    for ent in entities:
                        entity_id = entity_name_to_id.get(ent["name"])
                        if entity_id:
                            entity_records_to_insert.append({
                                "article_id": article_id,
                                "entity_id": entity_id,
                                "context": ent.get("context", ""),
                            })

                logger.debug(f"收集了 {len(entity_records_to_insert)} 条实体关联记录")
            except Exception as e:
                logger.warning(f"实体同步失败: {e}")

        # 提交第一个事务（新闻、关键词、实体同步）
        await session.commit()

        # 提交后校验：确认数据实际写入数据库
        verify_result = await session.execute(
            select(func.count(News.id)).where(News.link_hash.in_(list(hash_to_id.keys())))
        )
        verified_count = verify_result.scalar()
        if verified_count != saved:
            logger.error(f"数据校验失败: 预期 {saved} 条, 实际入库 {verified_count} 条")
        else:
            logger.debug(f"数据校验通过: {verified_count} 条已确认入库")

    # 在单独的事务中分批插入实体关联
    if entity_records_to_insert:
        try:
            inserted_count = await batch_insert_entity_relations(entity_records_to_insert)
            logger.info(f"实体关联插入完成: {inserted_count}/{len(entity_records_to_insert)} 条")
        except Exception as e:
            logger.warning(f"实体关联插入失败: {e}")

    # 清除相关缓存
    if saved > 0:
        _invalidate_news_cache()
    
    if events_saved > 0:
        _invalidate_events_cache()
        logger.info(f"Processed {events_saved} events")
    
    logger.info(f"批量插入完成: {saved} 篇新闻, {len(all_keyword_records)} 条关键词, {len(entity_records_to_insert)} 条实体关联待插入")
    return saved


def _invalidate_news_cache():
    """清除新闻相关缓存"""
    prefixes = [
        "api:news:",
        "api:categories:",
        "api:article-types:",
        "api:latest:",
        "api:meta",
        "api:keywords:",
        "api:entities:",
    ]
    for prefix in prefixes:
        invalidate_cache(prefix)


def _invalidate_events_cache():
    """清除事件相关缓存"""
    prefixes = [
        "api:events:",
    ]
    for prefix in prefixes:
        invalidate_cache(prefix)


async def process_article_event(session: AsyncSession, item: dict[str, any]) -> Optional[dict[str, any]]:
    """
    处理文章的事件检测和关联
    
    Args:
        session: 数据库会话
        item: 新闻数据
    
    Returns:
        事件信息或 None
    """
    title = item.get("title", "")
    summary = item.get("summary")
    content = item.get("content")
    category = item.get("category", "其他")
    pub_date = item.get("date")
    
    if isinstance(pub_date, datetime):
        pub_date = pub_date.date()
    elif not isinstance(pub_date, date):
        pub_date = date.today()
    
    # 检测事件
    event_info = detect_event_from_article(title, summary, content, category, pub_date)
    if not event_info:
        return None
    
    event_id = event_info["event_id"]
    
    try:
        # 查找已有事件
        result = await session.execute(
            select(Event).where(Event.event_id == event_id)
        )
        existing_event = result.scalar_one_or_none()
        
        if existing_event:
            # 更新已有事件
            related = existing_event.related_articles or []
            if not isinstance(related, list):
                related = []
            
            related.insert(0, {
                "title": title,
                "date": str(pub_date),
                "summary": summary[:100] if summary else None
            })
            related = related[:20]  # 只保留最近20篇
            
            existing_event.related_articles = related
            existing_event.update_count = (existing_event.update_count or 0) + 1
            existing_event.last_updated = pub_date
            
            # 如果标题更长，更新标题
            if len(title) > len(existing_event.title or ""):
                existing_event.title = title
            
            return {
                "event_id": event_id,
                "action": "updated",
                "update_count": existing_event.update_count
            }
        else:
            # 创建新事件
            new_event = Event(
                event_id=event_id,
                title=title,
                description=event_info["description"],
                category=category,
                first_seen=pub_date,
                last_updated=pub_date,
                update_count=1,
                status="active",
                related_articles=[],
                data={"event_type": event_info.get("event_type")}
            )
            session.add(new_event)
            
            return {
                "event_id": event_id,
                "action": "created"
            }
    
    except Exception as e:
        logger.error(f"Error processing event for article '{title}': {e}")
        return None


async def get_existing_hashes(days: int = 7, limit: int = 50000) -> set[str]:
    """
    获取最近 N 天的文章 hash 集合
    
    Args:
        days: 加载最近几天的数据，默认 7 天
        limit: 最大加载数量，默认 50000
    
    Returns:
        link_hash 集合
    """
    from datetime import timedelta
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    async with async_session() as session:
        result = await session.execute(
            select(News.link_hash)
            .where(News.created_at >= cutoff_date)
            .limit(limit)
        )
        return {row[0] for row in result.fetchall()}


async def get_existing_titles(category: str = None, limit: int = 500) -> list[str]:
    async with async_session() as session:
        query = select(News.title)
        if category:
            query = query.where(News.category == category)
        query = query.order_by(News.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return [row[0] for row in result.fetchall()]


async def update_source_health(
    source_name: str,
    success: bool,
    items_count: int = 0,
    error: Optional[str] = None,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> None:
    """更新源健康状态"""
    async with async_session() as session:
        result = await session.execute(select(SourceHealth).where(SourceHealth.source_name == source_name))
        health = result.scalar_one_or_none()
        if not health:
            health = SourceHealth(source_name=source_name)
            session.add(health)
        health.total_checks = (health.total_checks or 0) + 1
        health.last_check = datetime.now(timezone.utc)
        if success:
            health.total_success = (health.total_success or 0) + 1
            health.consecutive_failures = 0
            health.last_success = datetime.now(timezone.utc)
            health.last_items = items_count
        else:
            health.total_failure = (health.total_failure or 0) + 1
            health.consecutive_failures = (health.consecutive_failures or 0) + 1
            health.last_error = error
        if etag is not None:
            health.last_etag = etag
        if last_modified is not None:
            health.last_rss_modified = last_modified
        if health.total_checks > 0:
            health.success_rate = round((health.total_success or 0) / health.total_checks * 100, 2)
        await session.commit()


async def get_source_conditional_headers(source_name: str) -> dict:
    async with async_session() as session:
        result = await session.execute(select(SourceHealth).where(SourceHealth.source_name == source_name))
        health = result.scalar_one_or_none()
        if health:
            return {
                "etag": health.last_etag,
                "last_modified": health.last_rss_modified,
            }
        return {"etag": None, "last_modified": None}


async def batch_insert_entity_relations(records: List[Dict[str, Any]], batch_size: int = 500) -> int:
    """
    分批插入实体关联记录，避免 SQL 语句过于复杂
    
    Args:
        records: 实体关联记录列表
        batch_size: 每批插入的记录数
    
    Returns:
        成功插入的记录数
    """
    if not records:
        return 0
    
    from models.article_entity import ArticleEntity
    inserted = 0
    
    async with async_session() as session:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                stmt = (
                    pg_insert(ArticleEntity)
                    .values(batch)
                    .on_conflict_do_nothing()
                )
                await session.execute(stmt)
                inserted += len(batch)
            except Exception as e:
                logging.getLogger(__name__).warning(f"实体关联批次插入失败 (batch {i//batch_size + 1}): {e}")
                # 继续尝试下一批
        
        try:
            await session.commit()
        except Exception as e:
            logging.getLogger(__name__).error(f"实体关联事务提交失败: {e}")
            return 0
    
    return inserted
