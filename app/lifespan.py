"""
FastAPI 应用生命周期管理
统一管理启动/关闭时的资源初始化和清理
"""

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """应用生命周期：启动时初始化，关闭时清理"""
    # === 启动 ===
    logger.info("Application starting...")

    # 初始化数据库连接池（由 SQLAlchemy 自动管理）

    # 初始化翻译 HTTP 客户端
    try:
        from scraper.pipeline.translate import get_http_client
        await get_http_client()
        logger.info("Translation HTTP client initialized")
    except Exception as e:
        logger.warning(f"Failed to init translation client: {e}")

    logger.info("Application started")

    yield

    # === 关闭 ===
    logger.info("Application shutting down...")

    # 关闭翻译 HTTP 客户端
    try:
        from scraper.pipeline.translate import close_http_client
        await close_http_client()
        logger.info("Translation HTTP client closed")
    except Exception as e:
        logger.warning(f"Failed to close translation client: {e}")

    # 释放 spaCy 模型资源
    try:
        from scraper.pipeline.ner import close_models
        close_models()
        logger.info("spaCy models released")
    except Exception as e:
        logger.warning(f"Failed to release spaCy models: {e}")

    # 关闭数据库连接池
    try:
        from models.base import engine
        await engine.dispose()
        logger.info("Database engine disposed")
    except Exception as e:
        logger.warning(f"Failed to dispose database engine: {e}")

    logger.info("Application shutdown complete")
