import logging
from collections import defaultdict
from sqlalchemy import select, and_, or_
from models.article_keyword import ArticleKeyword
from models.article_relation import ArticleRelation

logger = logging.getLogger(__name__)

RELATION_THRESHOLD = 0.3


def _normalize_relation(source_id: int, target_id: int) -> tuple[int, int]:
    """
    规范化关系方向：确保 source_id < target_id
    这样可以避免存储重复的双向关系
    """
    if source_id > target_id:
        return target_id, source_id
    return source_id, target_id


async def get_article_keyword_ids(session, article_id: int) -> set[int]:
    """获取文章的关键词 ID 集合"""
    result = await session.execute(
        select(ArticleKeyword.keyword_id).where(ArticleKeyword.article_id == article_id)
    )
    return {row[0] for row in result.fetchall()}


async def calculate_and_save_relations(session, article_id: int, category: str):
    """
    计算并保存文章关联（优化版本）
    
    只存储一条关系记录（source_id < target_id），查询时使用 OR 条件获取所有相关关系。
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

    # 批量获取已有关系（单次查询，使用 OR 条件获取两个方向的关系）
    existing_result = await session.execute(
        select(
            ArticleRelation.source_id,
            ArticleRelation.target_id
        )
        .where(
            or_(
                ArticleRelation.source_id == article_id,
                ArticleRelation.target_id == article_id
            )
        )
    )
    
    # 构建已有关系集合（规范化方向）
    existing_relations = set()
    for row in existing_result:
        normalized = _normalize_relation(row[0], row[1])
        existing_relations.add(normalized)

    # 计算并保存关系
    new_relations = []
    for target_id, target_kw in candidate_keywords.items():
        # 规范化方向
        source, target = _normalize_relation(article_id, target_id)
        
        # 检查是否已存在
        if (source, target) in existing_relations:
            continue

        intersection = article_keywords & target_kw
        union = article_keywords | target_kw

        if not union:
            continue

        score = len(intersection) / len(union)

        if score >= RELATION_THRESHOLD:
            score_rounded = round(score, 4)
            
            # 只存储一条关系（source_id < target_id）
            new_relations.append(ArticleRelation(
                source_id=source,
                target_id=target,
                relation_type="keyword_match",
                score=score_rounded,
            ))
            
            # 添加到已存在集合，避免重复
            existing_relations.add((source, target))

    # 批量插入
    if new_relations:
        session.add_all(new_relations)
        logger.debug(f"Created {len(new_relations)} relations for article {article_id}")


async def get_related_article_ids(session, article_id: int) -> set[int]:
    """
    获取与指定文章相关的所有文章 ID
    
    Args:
        session: 数据库会话
        article_id: 文章 ID
    
    Returns:
        相关文章 ID 集合
    """
    result = await session.execute(
        select(
            ArticleRelation.source_id,
            ArticleRelation.target_id
        )
        .where(
            or_(
                ArticleRelation.source_id == article_id,
                ArticleRelation.target_id == article_id
            )
        )
    )
    
    related_ids = set()
    for row in result:
        # 返回另一个方向的文章 ID
        if row[0] == article_id:
            related_ids.add(row[1])
        else:
            related_ids.add(row[0])
    
    return related_ids
