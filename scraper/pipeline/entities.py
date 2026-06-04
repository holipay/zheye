import logging
import re
from pathlib import Path
from typing import Optional
from collections import defaultdict
import yaml

logger = logging.getLogger(__name__)

_entities_cache: Optional[dict] = None

NUMERIC_PATTERNS = [
    (r'\$[\d,.]+\s*(?:billion|million|trillion|B|M|T)\b', "currency"),
    (r'\$[\d,.]+', "currency"),
    (r'[\d,.]+\s*(?:billion|million|trillion)\s*(?:dollars|USD)\b', "currency"),
    (r'[\d,.]+\s*(?:billion|million|trillion)\s*(?:元|人民币)\b', "currency"),
    (r'[\d,.]+\s*(?:dollars|USD)\b', "currency"),
    (r'¥[\d,.]+', "currency"),
    (r'€[\d,.]+', "currency"),
    (r'[\d,.]+\s*(?:万亿|亿|万)\s*(?:元|人民币)?\b', "currency"),
    (r'[\d,.]+\s*%', "percentage"),
    (r'[\d,.]+\s*(?:percent|个百分点)\b', "percentage"),
    (r'[\d,.]+\s*(?:bp|bps|basis\s*points?)\b', "basis_point"),
    (r'[\d,.]+\s*(?:万亿|亿|万)\b', "large_number"),
]

_numeric_re = [(re.compile(p, re.IGNORECASE), t) for p, t in NUMERIC_PATTERNS]

# 预编译的实体别名正则缓存
_entity_patterns: Optional[dict[str, list[tuple[re.Pattern, str, str]]]] = None


def _build_entity_patterns(config: dict) -> dict[str, list[tuple[re.Pattern, str, str]]]:
    """
    预编译所有实体别名的正则表达式
    
    对短别名（<=3字符）使用严格边界匹配，避免误匹配
    
    Returns:
        {entity_type: [(compiled_pattern, entity_name, alias), ...]}
    """
    patterns = defaultdict(list)
    
    for entity_type in ["companies", "indicators", "organizations", "countries"]:
        entries = config.get(entity_type, [])
        if not isinstance(entries, list):
            continue
        
        for entry in entries:
            name = entry.get("name", "")
            aliases = entry.get("aliases", [])
            if not name or not aliases:
                continue
            
            for alias in aliases:
                if len(alias) < 2:
                    continue
                try:
                    if entity_type in ("companies", "organizations"):
                        # 短词使用严格边界（前后不能是字母）
                        if len(alias) <= 3:
                            pattern = re.compile(r'(?<![a-zA-Z])' + re.escape(alias) + r'(?![a-zA-Z])', re.IGNORECASE)
                        else:
                            # 使用词边界匹配
                            pattern = re.compile(r'\b' + re.escape(alias) + r'\b', re.IGNORECASE)
                    else:
                        # 使用简单包含匹配
                        pattern = re.compile(re.escape(alias), re.IGNORECASE)
                    patterns[entity_type].append((pattern, name, alias))
                except re.error:
                    continue
    
    return patterns


def load_entities() -> dict:
    global _entities_cache
    if _entities_cache is not None:
        return _entities_cache

    config_path = Path(__file__).parent.parent.parent / "configs" / "entities.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _entities_cache = yaml.safe_load(f)
            count = sum(len(v) for v in _entities_cache.values() if isinstance(v, list))
            logger.info(f"Loaded {count} entity entries from entities.yaml")
            return _entities_cache
    except Exception as e:
        logger.error(f"Error loading entities config: {e}")
        _entities_cache = {}
        return _entities_cache


def _get_entity_patterns() -> dict[str, list[tuple[re.Pattern, str, str]]]:
    """获取预编译的实体正则（懒加载）"""
    global _entity_patterns
    if _entity_patterns is None:
        config = load_entities()
        _entity_patterns = _build_entity_patterns(config)
    return _entity_patterns


TYPE_MAP = {
    "companies": "company",
    "indicators": "indicator",
    "organizations": "organization",
    "countries": "country",
}


def _get_context(text: str, match_start: int, match_end: int, max_len: int = 100) -> str:
    start = max(0, match_start - 30)
    end = min(len(text), match_end + 30)
    snippet = text[start:end].strip()
    return snippet[:max_len]


def extract_entities(title: str, summary: str = "", content: str = "") -> list[dict]:
    """
    从文本中提取实体
    
    使用预编译的正则表达式，提高匹配效率。
    """
    text = " ".join(filter(None, [title, summary, content]))
    if not text.strip():
        return []

    results = []
    seen = set()
    
    # 获取预编译的正则
    entity_patterns = _get_entity_patterns()

    for entity_type in ["companies", "indicators", "organizations", "countries"]:
        mapped_type = TYPE_MAP.get(entity_type, entity_type)
        
        for pattern, name, alias in entity_patterns.get(entity_type, []):
            if alias.lower() in seen:
                continue
            
            match = pattern.search(text)
            if match:
                seen.add(alias.lower())
                results.append({
                    "name": name,
                    "entity_type": mapped_type,
                    "context": _get_context(text, match.start(), match.end()),
                })

    numeric_spans = []
    for pattern, num_type in _numeric_re:
        for match in pattern.finditer(text):
            value = match.group().strip()
            if value.lower() in seen:
                continue

            is_overlapping = False
            for start, end in numeric_spans:
                if match.start() < end and match.end() > start:
                    is_overlapping = True
                    break
            if is_overlapping:
                continue

            seen.add(value.lower())
            numeric_spans.append((match.start(), match.end()))
            results.append({
                "name": value,
                "entity_type": num_type,
                "context": _get_context(text, match.start(), match.end()),
            })

    return results


async def sync_entities_to_db(session, entities: list[dict]) -> dict:
    """
    同步实体到数据库（优化版本，使用批量查询）
    """
    from sqlalchemy import select, tuple_
    from models.entity import Entity

    if not entities:
        return {}

    name_to_id = {}
    
    # 收集所有唯一的实体
    unique_entities = {}
    for ent in entities:
        normalized = ent["name"].lower().strip()
        entity_type = ent["entity_type"]
        cache_key = f"{normalized}:{entity_type}"
        if cache_key not in unique_entities:
            unique_entities[cache_key] = {
                "name": ent["name"],
                "normalized": normalized,
                "entity_type": entity_type,
            }
    
    # 批量查询已有实体
    keys = [(v["normalized"], v["entity_type"]) for v in unique_entities.values()]
    if keys:
        result = await session.execute(
            select(Entity).where(
                tuple_(Entity.normalized_name, Entity.entity_type).in_(keys)
            )
        )
        existing = {(e.normalized_name, e.entity_type): e.id for e in result.scalars()}
    else:
        existing = {}
    
    # 处理每个实体
    new_entities = []
    for cache_key, ent in unique_entities.items():
        normalized = ent["normalized"]
        entity_type = ent["entity_type"]
        
        if (normalized, entity_type) in existing:
            name_to_id[cache_key] = existing[(normalized, entity_type)]
        else:
            # 创建新实体
            new_entity = Entity(
                name=ent["name"],
                entity_type=entity_type,
                normalized_name=normalized,
            )
            new_entities.append(new_entity)
            session.add(new_entity)
    
    # 批量刷新获取 ID
    if new_entities:
        await session.flush()
        for e in new_entities:
            cache_key = f"{e.normalized_name}:{e.entity_type}"
            name_to_id[cache_key] = e.id

    return name_to_id


async def save_article_entities(session, article_id: int, entities: list[dict], name_to_id: dict):
    """
    保存文章实体关联（优化版本，使用批量查询）
    """
    from sqlalchemy import select, and_
    from models.article_entity import ArticleEntity

    if not entities:
        return
    
    # 收集要插入的实体
    entity_ids = []
    entity_contexts = {}
    for ent in entities:
        normalized = ent["name"].lower().strip()
        cache_key = f"{normalized}:{ent['entity_type']}"
        entity_id = name_to_id.get(cache_key)
        if entity_id:
            entity_ids.append(entity_id)
            entity_contexts[entity_id] = ent.get("context")
    
    if not entity_ids:
        return
    
    # 批量查询已有关联
    result = await session.execute(
        select(ArticleEntity.entity_id).where(
            and_(
                ArticleEntity.article_id == article_id,
                ArticleEntity.entity_id.in_(entity_ids)
            )
        )
    )
    existing_ids = {row[0] for row in result.fetchall()}
    
    # 批量创建新关联
    new_entities = []
    for entity_id in entity_ids:
        if entity_id not in existing_ids:
            new_entities.append(ArticleEntity(
                article_id=article_id,
                entity_id=entity_id,
                context=entity_contexts.get(entity_id),
                relevance=1.0,
            ))
    
    if new_entities:
        session.add_all(new_entities)
