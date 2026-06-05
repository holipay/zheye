"""
公共工具模块
从共享模块导入，保持向后兼容
"""

# 从共享模块导入所有公共函数
from common.utils import (
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
