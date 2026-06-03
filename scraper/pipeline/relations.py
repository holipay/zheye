import logging
from collections import defaultdict
from sqlalchemy import select, and_
from models.article_keyword import ArticleKeyword
from models.article_relation import ArticleRelation

logger = logging.getLogger(__name__)

RELATION_THRESHOLD = 0.3


async def get_article_keyword_ids(session, article_id: int) -> set[int]:
    """获取文章的关键词 ID 集合"""
    result = await session.execute(
        select(ArticleKeyword.keyword_id).where(ArticleKeyword.article_id == article_id)
    )
    return {row[0] for row in result.fetchall()}


async def calculate_and_save_relations(session, article_id: int, category: str):
    """
    计算并保存文章关联（优化版本，避免 N+1 查询）
    
    使用批量查询一次性获取所有候选文章的关键词，减少数据库往返。
    """
    # 获取当前文章的关键词
    article_keywords = await get_article_keyword_ids(session, article_id)
    if not article_keywords:
        return

    # 批量获取所有候选文章的关键词（单次查询）
    result = await session.execute(
        select(ArticleKeyword.article_id, ArticleKeyword.keyword_id)
        .where(ArticleKeyword.keyword_id.in_(article_keywords))
        .where(ArticleKeyword.article_id != article_id)
    )
    
    # 在内存中按文章分组
    candidate_keywords: dict[int, set[int]] = defaultdict(set)
    for row in result:
        candidate_keywords[row[0]].add(row[1])

    if not candidate_keywords:
        return

    # 批量获取已有关系（单次查询）
    existing_result = await session.execute(
        select(ArticleRelation.target_id)
        .where(ArticleRelation.source_id == article_id)
    )
    existing_targets = {row[0] for row in existing_result.fetchall()}

    # 批量获取已有反向关系（单次查询）
    reverse_existing_result = await session.execute(
        select(ArticleRelation.source_id)
        .where(
            ArticleRelation.target_id == article_id,
            ArticleRelation.source_id.in_(list(candidate_keywords.keys()))
        )
    )
    reverse_existing = {row[0] for row in reverse_existing_result.fetchall()}

    # 计算并保存关系
    new_relations = []
    for target_id, target_kw in candidate_keywords.items():
        if target_id in existing_targets:
            continue

        intersection = article_keywords & target_kw
        union = article_keywords | target_kw

        if not union:
            continue

        score = len(intersection) / len(union)

        if score >= RELATION_THRESHOLD:
            score_rounded = round(score, 4)
            
            # 正向关系
            new_relations.append(ArticleRelation(
                source_id=article_id,
                target_id=target_id,
                relation_type="keyword_match",
                score=score_rounded,
            ))
            
            # 反向关系（如果不存在）
            if target_id not in reverse_existing:
                new_relations.append(ArticleRelation(
                    source_id=target_id,
                    target_id=article_id,
                    relation_type="keyword_match",
                    score=score_rounded,
                ))

    # 批量插入
    if new_relations:
        session.add_all(new_relations)
        logger.debug(f"Created {len(new_relations)} relations for article {article_id}")
