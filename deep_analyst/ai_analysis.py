"""
AI 分析服务模块（deep_analyst 版本）

复用 scraper.pipeline.ai_analysis 中的 DeepSeekClient，
避免代码重复。
"""

from scraper.pipeline.ai_analysis import (
    ArticleAnalysis,
    DeepSeekClient,
    get_ai_client,
    is_ai_enabled,
)

__all__ = [
    "ArticleAnalysis",
    "DeepSeekClient",
    "get_ai_client",
    "is_ai_enabled",
]
