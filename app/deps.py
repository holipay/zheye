"""
FastAPI 依赖注入
统一管理 AI 客户端等共享资源
"""

from scraper.pipeline.ai_analysis import DeepSeekClient, get_ai_client


def get_ai_client_dependency() -> DeepSeekClient:
    """获取 AI 客户端单例（用于 FastAPI Depends）"""
    return get_ai_client()
