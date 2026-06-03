import hashlib
import logging
from collections import defaultdict

from scraper.pipeline.utils import text_similarity
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = settings.DEDUP_THRESHOLD


def get_link_hash(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def similarity(a: str, b: str) -> float:
    return text_similarity(a, b)


def _get_ngrams(text: str, n: int = 3) -> set[str]:
    """提取文本的 n-gram 集合，用于快速预筛选"""
    text = text.lower().strip()
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def _ngram_similarity(a: str, b: str, n: int = 3) -> float:
    """基于 n-gram 的快速相似度估算"""
    ngrams_a = _get_ngrams(a, n)
    ngrams_b = _get_ngrams(b, n)
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection = len(ngrams_a & ngrams_b)
    union = len(ngrams_a | ngrams_b)
    return intersection / union if union > 0 else 0.0


def is_duplicate(title: str, existing_titles: list[str], threshold: float = DEFAULT_THRESHOLD) -> bool:
    """
    检查标题是否重复
    使用两阶段策略：
    1. 快速 n-gram 预筛选，过滤明显不相似的候选
    2. 对候选进行精确相似度计算
    """
    if not title or not existing_titles:
        return False
    
    # 预筛选阈值：比最终阈值低一些，确保召回率
    prefilter_threshold = threshold * 0.6
    
    for existing in existing_titles:
        # 第一阶段：快速 n-gram 预筛选
        ngram_sim = _ngram_similarity(title, existing)
        if ngram_sim < prefilter_threshold:
            continue
        
        # 第二阶段：精确相似度计算
        if similarity(title, existing) >= threshold:
            return True
    
    return False
