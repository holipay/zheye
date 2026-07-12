"""
批处理管道
遍历已配置的跟踪企业，拉取未处理的新闻，执行贝叶斯更新
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_tracker.bayesian import (
    DEFAULT_DIMENSIONS,
    BeliefEngine,
    BeliefState,
)
from business_tracker.evidence import process_article_evidence
from business_tracker.models.company import TrackedCompany
from business_tracker.models.dimension import CompanyDimension
from business_tracker.models.evidence import EvidenceRecord
from business_tracker.models.history import BeliefHistory
from business_tracker.priors import prior_from_market_data
from models.article_entity import ArticleEntity
from models.base import async_session
from models.entity import Entity
from models.news import News
from scraper.pipeline.ai_analysis import get_ai_client

logger = logging.getLogger(__name__)


async def get_entity_id_for_company(session: AsyncSession, tracked: TrackedCompany) -> int:
    return tracked.entity_id


async def init_company_dimensions(
    session: AsyncSession,
    company_id: int,
    stock_symbol: str = "",
):
    priors = await prior_from_market_data(session, stock_symbol)

    for dim in DEFAULT_DIMENSIONS:
        state = priors.get(dim, BeliefState(alpha=2.0, beta=2.0))
        result = await session.execute(
            select(CompanyDimension).where(
                CompanyDimension.company_id == company_id,
                CompanyDimension.dimension == dim,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            cd = CompanyDimension(
                company_id=company_id,
                dimension=dim,
                alpha=state.alpha,
                beta=state.beta,
                mean=state.mean,
                variance=state.variance,
                updated_by="prior",
            )
            session.add(cd)


def _save_belief_history(session: AsyncSession, company_id: int, dim: str, state: BeliefState):
    bh = BeliefHistory(
        company_id=company_id,
        dimension=dim,
        alpha=state.alpha,
        beta=state.beta,
        mean=state.mean,
        variance=state.variance,
    )
    session.add(bh)


async def process_company(session: AsyncSession, tracked: TrackedCompany):
    entity_id = tracked.entity_id
    config = tracked.config or {}
    stock_symbol = config.get("stock_symbol", "")
    use_llm = config.get("use_llm", False)

    entity_result = await session.execute(
        select(Entity).where(Entity.id == entity_id)
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        logger.warning(f"Entity {entity_id} not found for tracked company {tracked.id}")
        return

    company_name = entity.name

    # 确保维度记录存在
    dim_result = await session.execute(
        select(CompanyDimension).where(CompanyDimension.company_id == tracked.id)
    )
    existing_dims = {d.dimension: d for d in dim_result.scalars().all()}

    if not existing_dims:
        await init_company_dimensions(session, tracked.id, stock_symbol)
        await session.flush()
        dim_result = await session.execute(
            select(CompanyDimension).where(CompanyDimension.company_id == tracked.id)
        )
        existing_dims = {d.dimension: d for d in dim_result.scalars().all()}

    # 查找已有证据，跳过已处理新闻
    evidence_result = await session.execute(
        select(EvidenceRecord.news_id).where(EvidenceRecord.company_id == tracked.id)
    )
    processed_news_ids = {row[0] for row in evidence_result.fetchall()}

    # 查找与该实体关联的未处理新闻
    articles_query = (
        select(News)
        .join(ArticleEntity, ArticleEntity.article_id == News.id)
        .where(ArticleEntity.entity_id == entity_id)
        .where(News.id.notin_(processed_news_ids) if processed_news_ids else True)
        .where(News.ai_analyzed_at.isnot(None))
        .order_by(News.date.desc())
        .limit(200)
    )
    articles_result = await session.execute(articles_query)
    articles = articles_result.scalars().all()

    if not articles:
        logger.info(f"No new articles for {company_name}")
        return

    ai_client = get_ai_client() if use_llm else None

    for article in articles:
        evidence_map = await process_article_evidence(
            article, company_name, ai_client, use_llm
        )

        for dim, (strength, pos_ratio, neg_ratio) in evidence_map.items():
            dim_record = existing_dims.get(dim)
            if not dim_record:
                continue

            state = BeliefState(alpha=dim_record.alpha, beta=dim_record.beta)
            engine = BeliefEngine(alpha=state.alpha, beta=state.beta)
            new_state = engine.update(strength, pos_ratio, neg_ratio)

            dim_record.alpha = new_state.alpha
            dim_record.beta = new_state.beta
            dim_record.mean = new_state.mean
            dim_record.variance = new_state.variance
            dim_record.updated_by = "llm" if use_llm and article.ai_importance and article.ai_importance >= 0.6 else "sentiment"

            direction = "positive" if pos_ratio > 0.5 else "negative"
            if abs(pos_ratio - 0.5) < 0.01:
                direction = "neutral"

            ev = EvidenceRecord(
                company_id=tracked.id,
                news_id=article.id,
                dimension=dim,
                direction=direction,
                strength=strength,
                confidence=pos_ratio if direction == "positive" else neg_ratio,
                source=dim_record.updated_by,
            )
            session.add(ev)

            _save_belief_history(session, tracked.id, dim, new_state)

    logger.info(
        f"Processed {len(articles)} articles for {company_name}, "
        f"updated {len(evidence_map) * len(articles)} evidence records"
    )


async def process_all_companies():
    async with async_session() as session:
        try:
            result = await session.execute(
                select(TrackedCompany).where(TrackedCompany.is_active.is_(True))
            )
            companies = result.scalars().all()

            if not companies:
                logger.info("No active tracked companies found")
                return

            for tracked in companies:
                try:
                    await process_company(session, tracked)
                    await session.flush()
                except Exception as e:
                    logger.error(f"Failed to process company {tracked.id}: {e}")
                    await session.rollback()
                    continue

            await session.commit()
            logger.info(f"Belief update completed for {len(companies)} companies")
        except Exception as e:
            await session.rollback()
            logger.error(f"Belief update pipeline failed: {e}")
            raise
