import hashlib
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.75


def get_link_hash(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_duplicate(title: str, existing_titles: list[str], threshold: float = DEFAULT_THRESHOLD) -> bool:
    for existing in existing_titles:
        if similarity(title, existing) >= threshold:
            return True
    return False
