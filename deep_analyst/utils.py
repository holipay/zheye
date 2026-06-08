"""
公共工具模块（deep_analyst 版本）
复用 scraper.pipeline.utils 中的定义，避免重复。
"""

from scraper.pipeline.utils import (
    smart_truncate,
    parse_ai_response,
    ai_analyze,
    format_article_summaries,
    text_similarity,
    calculate_confidence,
)

__all__ = [
    "smart_truncate",
    "parse_ai_response",
    "ai_analyze",
    "format_article_summaries",
    "text_similarity",
    "calculate_confidence",
]
