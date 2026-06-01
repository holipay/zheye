import logging
import re
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)

_keywords_cache: Optional[list[dict]] = None


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


def match_keywords(title: str, translated_title: str, summary: str, category: str) -> list[dict]:
    keywords = load_keywords()
    if not keywords:
        return []

    text_parts = [title or "", translated_title or "", summary or ""]
    text = " ".join(text_parts).lower()

    if not text.strip():
        return []

    matched = []
    matched_same_category = []
    matched_cross_category = []

    for kw in keywords:
        term = kw["term"]
        kw_category = kw.get("category", "")
        lang = kw.get("lang", "en")
        weight = kw.get("weight", 1.0)

        is_same_category = kw_category and category and kw_category == category

        if lang == "en":
            if len(term) < 3:
                continue
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
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
        else:
            if len(term) < 2:
                continue
            if term.lower() in text:
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

    if matched_same_category:
        matched = matched_same_category
    else:
        matched = matched_cross_category

    seen = set()
    unique_matched = []
    for m in matched:
        if m["term"] not in seen:
            seen.add(m["term"])
            unique_matched.append(m)

    return unique_matched


async def sync_keywords_to_db(session, keywords_data: list[dict]) -> dict:
    from sqlalchemy import select
    from models.keyword import Keyword

    term_to_id = {}

    for kw_data in keywords_data:
        term = kw_data["term"]
        lang = kw_data.get("lang", "en")
        category = kw_data.get("category", "")
        weight = kw_data.get("weight", 1.0)

        result = await session.execute(
            select(Keyword).where(Keyword.term == term, Keyword.lang == lang)
        )
        existing = result.scalar_one_or_none()

        if existing:
            term_to_id[term] = existing.id
        else:
            new_kw = Keyword(term=term, lang=lang, category=category, weight=weight)
            session.add(new_kw)
            await session.flush()
            term_to_id[term] = new_kw.id

    return term_to_id


async def save_article_keywords(session, article_id: int, matched_keywords: list[dict], term_to_id: dict):
    from sqlalchemy import select
    from models.article_keyword import ArticleKeyword

    for mk in matched_keywords:
        term = mk["term"]
        keyword_id = term_to_id.get(term)
        if not keyword_id:
            continue

        result = await session.execute(
            select(ArticleKeyword).where(
                ArticleKeyword.article_id == article_id,
                ArticleKeyword.keyword_id == keyword_id,
            )
        )
        existing = result.scalar_one_or_none()

        if not existing:
            ak = ArticleKeyword(
                article_id=article_id,
                keyword_id=keyword_id,
                relevance=mk.get("relevance", 1.0),
            )
            session.add(ak)
