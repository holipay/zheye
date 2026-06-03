import hashlib
import logging

from scraper.pipeline.utils import text_similarity

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.75


def get_link_hash(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def similarity(a: str, b: str) -> float:
    return text_similarity(a, b)


def is_duplicate(title: str, existing_titles: list[str], threshold: float = DEFAULT_THRESHOLD) -> bool:
    for existing in existing_titles:
        if similarity(title, existing) >= threshold:
            return True
    return False
