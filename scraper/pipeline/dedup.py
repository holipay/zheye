import hashlib
import logging
from collections import defaultdict
from typing import Optional

from app.config import settings
from scraper.pipeline.utils import text_similarity

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = settings.DEDUP_THRESHOLD

# TF-IDF 去重配置
USE_TFIDF_DEDUP = settings.USE_TFIDF_DEDUP

# 全局去重器实例
_tfidf_deduplicator = None


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


def _get_tfidf_deduplicator(threshold: float = DEFAULT_THRESHOLD):
    """获取全局 TF-IDF 去重器实例"""
    global _tfidf_deduplicator
    if _tfidf_deduplicator is None:
        try:
            from scraper.pipeline.tfidf_dedup import TFIDFDeduplicator
            _tfidf_deduplicator = TFIDFDeduplicator(threshold=threshold)
        except Exception as e:
            logger.warning(f"Failed to create TF-IDF deduplicator: {e}")
    return _tfidf_deduplicator


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
            dedup = _get_tfidf_deduplicator(threshold)
            if dedup:
                # 只在矩阵未构建或标题数量变化较大时重新 fit
                if not dedup._is_fitted or abs(len(dedup._titles) - len(existing_titles)) > 50:
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


def add_to_dedup_cache(title: str):
    """将新标题添加到去重缓存"""
    global _tfidf_deduplicator
    if _tfidf_deduplicator and title:
        try:
            _tfidf_deduplicator.add_title(title)
        except Exception as e:
            logger.debug(f"Failed to add title to dedup cache: {e}")
