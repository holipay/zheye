import logging
from sqlalchemy import select
from models.article_keyword import ArticleKeyword
from models.article_relation import ArticleRelation

logger = logging.getLogger(__name__)

RELATION_THRESHOLD = 0.3


async def get_article_keyword_ids(session, article_id: int) -> set[int]:
    result = await session.execute(
        select(ArticleKeyword.keyword_id).where(ArticleKeyword.article_id == article_id)
    )
    return {row[0] for row in result.fetchall()}


async def calculate_and_save_relations(session, article_id: int, category: str):
    article_keywords = await get_article_keyword_ids(session, article_id)
    if not article_keywords:
        return

    result = await session.execute(
        select(
            ArticleKeyword.article_id,
        )
        .where(ArticleKeyword.keyword_id.in_(article_keywords))
        .where(ArticleKeyword.article_id != article_id)
        .distinct()
    )
    candidate_ids = [row[0] for row in result.fetchall()]

    if not candidate_ids:
        return

    existing_result = await session.execute(
        select(ArticleRelation.target_id).where(ArticleRelation.source_id == article_id)
    )
    existing_targets = {row[0] for row in existing_result.fetchall()}

    for target_id in candidate_ids:
        if target_id in existing_targets:
            continue

        target_keywords = await get_article_keyword_ids(session, target_id)
        if not target_keywords:
            continue

        intersection = article_keywords & target_keywords
        union = article_keywords | target_keywords

        if not union:
            continue

        score = len(intersection) / len(union)

        if score >= RELATION_THRESHOLD:
            relation = ArticleRelation(
                source_id=article_id,
                target_id=target_id,
                relation_type="keyword_match",
                score=round(score, 4),
            )
            session.add(relation)

            reverse_relation = ArticleRelation(
                source_id=target_id,
                target_id=article_id,
                relation_type="keyword_match",
                score=round(score, 4),
            )
            existing_reverse = await session.execute(
                select(ArticleRelation).where(
                    ArticleRelation.source_id == target_id,
                    ArticleRelation.target_id == article_id,
                )
            )
            if not existing_reverse.scalar_one_or_none():
                session.add(reverse_relation)

    logger.debug(f"Processed relations for article {article_id}")
