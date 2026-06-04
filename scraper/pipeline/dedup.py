import hashlib
import logging
from collections import defaultdict

from app.config import settings
from scraper.pipeline.utils import text_similarity

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = settings.DEDUP_THRESHOLD

# TF-IDF 去重配置
USE_TFIDF_DEDUP = settings.USE_TFIDF_DEDUP


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


def is_duplicate(title: str, existing_titles: list[str], threshold: float = DEFAULT_THRESHOLD, use_tfidf: bool = None) -> bool:
    """
    检查标题是否重复
    
    使用混合策略：
    1. 如果启用 TF-IDF，使用语义去重
    2. 否则使用传统 n-gram + 精确相似度
    
    Args:
        title: 待检查的标题
        existing_titles: 已有标题列表
        threshold: 相似度阈值
        use_tfidf: 是否使用 TF-IDF（None 时使用环境变量配置）
    """
    if not title or not existing_titles:
        return False
    
    # 是否使用 TF-IDF
    if use_tfidf is None:
        use_tfidf = USE_TFIDF_DEDUP
    
    if use_tfidf:
        try:
            from scraper.pipeline.tfidf_dedup import TFIDFDeduplicator
            # 每次调用创建新实例，避免状态污染
            dedup = TFIDFDeduplicator(threshold=threshold)
            dedup.fit(existing_titles)
            return dedup.is_duplicate(title)
        except Exception as e:
            logger.warning(f"TF-IDF 去重失败，降级到传统方法: {e}")
    
    # 传统方法：n-gram 预筛选 + 精确相似度
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
