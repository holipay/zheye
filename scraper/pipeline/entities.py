import logging
import re
from pathlib import Path
from typing import Optional
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
    config = load_entities()
    if not config:
        return []

    text = " ".join(filter(None, [title, summary, content]))
    if not text.strip():
        return []

    results = []
    seen = set()

    for entity_type in ["companies", "indicators", "organizations", "countries"]:
        entries = config.get(entity_type, [])
        if not isinstance(entries, list):
            continue
        mapped_type = TYPE_MAP.get(entity_type, entity_type)

        for entry in entries:
            name = entry.get("name", "")
            aliases = entry.get("aliases", [])
            if not name or not aliases:
                continue

            for alias in aliases:
                if len(alias) < 2:
                    continue

                if alias.lower() in seen:
                    continue

                if entity_type in ("companies", "organizations"):
                    pattern = r'\b' + re.escape(alias) + r'\b'
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        seen.add(alias.lower())
                        results.append({
                            "name": name,
                            "entity_type": mapped_type,
                            "context": _get_context(text, match.start(), match.end()),
                        })
                        break
                else:
                    if alias.lower() in text.lower():
                        idx = text.lower().index(alias.lower())
                        seen.add(alias.lower())
                        results.append({
                            "name": name,
                            "entity_type": mapped_type,
                            "context": _get_context(text, idx, idx + len(alias)),
                        })
                        break

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
    from sqlalchemy import select
    from models.entity import Entity

    name_to_id = {}

    for ent in entities:
        name = ent["name"]
        entity_type = ent["entity_type"]
        normalized = name.lower().strip()
        cache_key = f"{normalized}:{entity_type}"

        if cache_key in name_to_id:
            continue

        result = await session.execute(
            select(Entity).where(
                Entity.normalized_name == normalized,
                Entity.entity_type == entity_type,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            name_to_id[cache_key] = existing.id
        else:
            new_entity = Entity(
                name=name,
                entity_type=entity_type,
                normalized_name=normalized,
            )
            session.add(new_entity)
            await session.flush()
            name_to_id[cache_key] = new_entity.id

    return name_to_id


async def save_article_entities(session, article_id: int, entities: list[dict], name_to_id: dict):
    from sqlalchemy import select
    from models.article_entity import ArticleEntity

    for ent in entities:
        normalized = ent["name"].lower().strip()
        cache_key = f"{normalized}:{ent['entity_type']}"
        entity_id = name_to_id.get(cache_key)
        if not entity_id:
            continue

        result = await session.execute(
            select(ArticleEntity).where(
                ArticleEntity.article_id == article_id,
                ArticleEntity.entity_id == entity_id,
            )
        )
        existing = result.scalar_one_or_none()

        if not existing:
            ae = ArticleEntity(
                article_id=article_id,
                entity_id=entity_id,
                context=ent.get("context"),
                relevance=1.0,
            )
            session.add(ae)
