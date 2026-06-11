import logging
import re
from pathlib import Path
from typing import Optional
from collections import defaultdict
import yaml

logger = logging.getLogger(__name__)

_keywords_cache: Optional[list[dict]] = None

# 预编译的关键词正则缓存
_keyword_patterns: Optional[dict[str, list[tuple[re.Pattern, dict]]]] = None


def _build_keyword_patterns(keywords: list[dict]) -> dict[str, list[tuple[re.Pattern, dict]]]:
    """
    预编译所有关键词的正则表达式
    
    对短词（<=3字符）使用严格边界匹配，避免误匹配：
    - "AI" 不会匹配 "said", "paid", "main"
    - "US" 不会匹配 "industry", "bonus"
    
    Returns:
        {lang: [(compiled_pattern, keyword_data), ...]}
    """
    patterns = defaultdict(list)
    
    for kw in keywords:
        term = kw["term"]
        lang = kw.get("lang", "en")
        
        try:
            if lang == "en":
                if len(term) < 2:
                    continue
                # 短词使用严格边界（前后不能是字母）
                if len(term) <= 3:
                    pattern = re.compile(r'(?<![a-zA-Z])' + re.escape(term) + r'(?![a-zA-Z])', re.IGNORECASE)
                else:
                    pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            else:
                if len(term) < 2:
                    continue
                pattern = re.compile(re.escape(term), re.IGNORECASE)
            
            patterns[lang].append((pattern, kw))
        except re.error:
            continue
    
    return patterns


def load_keywords() -> list[dict]:
    global _keywords_cache
    if _keywords_cache is not None:
        return _keywords_cache

    config_path = Path(__file__).parent.parent.parent / "configs" / "keywords.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            _keywords_cache = data.get("keywords", [])
            logger.info(f"Loaded {len(_keywords_cache)} keywords from lexicon")
            return _keywords_cache
    except Exception as e:
        logger.error(f"Error loading keywords config: {e}")
        _keywords_cache = []
        return _keywords_cache


def _get_keyword_patterns() -> dict[str, list[tuple[re.Pattern, dict]]]:
    """获取预编译的关键词正则（懒加载）"""
    global _keyword_patterns
    if _keyword_patterns is None:
        keywords = load_keywords()
        _keyword_patterns = _build_keyword_patterns(keywords)
    return _keyword_patterns


def match_keywords(title: str, translated_title: str, summary: str, category: str, content: str = None) -> list[dict]:
    """
    匹配关键词（使用预编译正则）
    """
    title_text = " ".join([title or "", translated_title or "", summary or ""]).lower()
    full_text = (title_text + " " + (content or "")).lower()

    if not full_text.strip():
        return []

    matched_same_category = []
    matched_cross_category = []
    
    # 获取预编译的正则
    keyword_patterns = _get_keyword_patterns()

    for lang, patterns in keyword_patterns.items():
        for pattern, kw in patterns:
            term = kw["term"]
            kw_category = kw.get("category", "")
            weight = kw.get("weight", 1.0)

            is_same_category = kw_category and category and kw_category == category

            # 检查标题
            in_title = pattern.search(title_text)
            if in_title:
                entry = {
                    "term": term,
                    "keyword_id": None,
                    "weight": weight,
                    "relevance": weight if is_same_category else weight * 0.8,
                }
                if is_same_category:
                    matched_same_category.append(entry)
                else:
                    matched_cross_category.append(entry)
                continue
            
            # 检查内容
            if content:
                in_content = pattern.search(full_text)
                if in_content:
                    entry = {
                        "term": term,
                        "keyword_id": None,
                        "weight": weight,
                        "relevance": weight * 0.5 if is_same_category else weight * 0.4,
                    }
                    if is_same_category:
                        matched_same_category.append(entry)
                    else:
                        matched_cross_category.append(entry)

    # 优先返回同分类的匹配
    if matched_same_category:
        matched = matched_same_category
    else:
        matched = matched_cross_category

    # 去重
    seen = set()
    unique_matched = []
    for m in matched:
        if m["term"] not in seen:
            seen.add(m["term"])
            unique_matched.append(m)

    return unique_matched


async def sync_keywords_to_db(session, keywords_data: list[dict]) -> dict:
    """
    同步关键词到数据库（优化版本，使用批量查询）
    """
    from sqlalchemy import select, tuple_
    from models.keyword import Keyword

    if not keywords_data:
        return {}

    term_to_id = {}
    
    # 收集所有唯一的关键词
    unique_keywords = {}
    for kw_data in keywords_data:
        term = kw_data["term"]
        lang = kw_data.get("lang", "en")
        if term not in unique_keywords:
            unique_keywords[term] = {
                "term": term,
                "lang": lang,
                "category": kw_data.get("category", ""),
                "weight": kw_data.get("weight", 1.0),
            }
    
    # 批量查询已有关键词
    keys = [(v["term"], v["lang"]) for v in unique_keywords.values()]
    if keys:
        result = await session.execute(
            select(Keyword).where(
                tuple_(Keyword.term, Keyword.lang).in_(keys)
            )
        )
        existing = {(k.term, k.lang): k.id for k in result.scalars()}
    else:
        existing = {}
    
    # 处理每个关键词
    new_keywords = []
    for term, kw in unique_keywords.items():
        lang = kw["lang"]
        
        if (term, lang) in existing:
            term_to_id[term] = existing[(term, lang)]
        else:
            new_kw = Keyword(
                term=term,
                lang=lang,
                category=kw["category"],
                weight=kw["weight"]
            )
            new_keywords.append(new_kw)
            session.add(new_kw)
    
    # 批量刷新获取 ID
    if new_keywords:
        await session.flush()
        for k in new_keywords:
            term_to_id[k.term] = k.id

    return term_to_id


async def save_article_keywords(session, article_id: int, matched_keywords: list[dict], term_to_id: dict):
    """
    保存文章关键词关联（优化版本，使用批量查询）
    """
    from sqlalchemy import select, and_
    from models.article_keyword import ArticleKeyword

    if not matched_keywords:
        return
    
    # 收集要插入的关键词
    keyword_ids = []
    keyword_relevance = {}
    for mk in matched_keywords:
        term = mk["term"]
        keyword_id = term_to_id.get(term)
        if keyword_id:
            keyword_ids.append(keyword_id)
            keyword_relevance[keyword_id] = mk.get("relevance", 1.0)
    
    if not keyword_ids:
        return
    
    # 批量查询已有关联
    result = await session.execute(
        select(ArticleKeyword.keyword_id).where(
            and_(
                ArticleKeyword.article_id == article_id,
                ArticleKeyword.keyword_id.in_(keyword_ids)
            )
        )
    )
    existing_ids = {row[0] for row in result.fetchall()}
    
    # 批量创建新关联
    new_keywords = []
    for keyword_id in keyword_ids:
        if keyword_id not in existing_ids:
            new_keywords.append(ArticleKeyword(
                article_id=article_id,
                keyword_id=keyword_id,
                relevance=keyword_relevance.get(keyword_id, 1.0),
            ))
    
    if new_keywords:
        session.add_all(new_keywords)
