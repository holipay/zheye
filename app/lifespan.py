"""
FastAPI 应用生命周期管理
统一管理启动/关闭时的资源初始化和清理
"""

import logging
from contextlib import asynccontextmanager

from app.config import settings

logger = logging.getLogger(__name__)


async def scheduled_scrape():
    """定时任务：抓取新闻"""
    try:
        from scraper.run_news import main as scrape_main
        logger.info("Scheduled: starting news scrape")
        await scrape_main()
        logger.info("Scheduled: news scrape completed")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}")


async def scheduled_daily_analysis():
    """定时任务：每日 AI 分析"""
    try:
        from scripts.run_daily_analysis import main as analysis_main
        logger.info("Scheduled: starting daily analysis")
        await analysis_main()
        logger.info("Scheduled: daily analysis completed")
    except Exception as e:
        logger.error(f"Scheduled daily analysis failed: {e}")


async def scheduled_cleanup():
    """定时任务：清理旧数据"""
    try:
        from scripts.cleanup_old_data import main as cleanup_main
        logger.info("Scheduled: starting data cleanup")
        await cleanup_main()
        logger.info("Scheduled: data cleanup completed")
    except Exception as e:
        logger.error(f"Scheduled cleanup failed: {e}")


@asynccontextmanager
async def lifespan(app):
    """应用生命周期：启动时初始化，关闭时清理"""
    # === 启动 ===
    logger.info("Application starting...")

    # 初始化翻译 HTTP 客户端
    try:
        from scraper.pipeline.translate import get_http_client
        await get_http_client()
        logger.info("Translation HTTP client initialized")
    except Exception as e:
        logger.warning(f"Failed to init translation client: {e}")

    # 启动定时任务调度器
    scheduler = None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler()

        # 每天 0:00 和 12:00 抓取新闻
        scheduler.add_job(scheduled_scrape, CronTrigger(hour="0,12"), id="scrape_news")

        # 每天凌晨 2:00 执行 AI 分析
        scheduler.add_job(scheduled_daily_analysis, CronTrigger(hour=2), id="daily_analysis")

        # 每天凌晨 3:00 清理旧数据
        scheduler.add_job(scheduled_cleanup, CronTrigger(hour=3), id="cleanup")

        scheduler.start()
        logger.info("Scheduler started with 3 jobs")
    except Exception as e:
        logger.warning(f"Failed to start scheduler: {e}")

    logger.info("Application started")

    yield

    # === 关闭 ===
    logger.info("Application shutting down...")

    # 停止调度器
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.warning(f"Failed to stop scheduler: {e}")

    # 关闭翻译 HTTP 客户端
    try:
        from scraper.pipeline.translate import close_http_client
        await close_http_client()
        logger.info("Translation HTTP client closed")
    except Exception as e:
        logger.warning(f"Failed to close translation client: {e}")

    # 关闭市场数据 API 共享客户端
    try:
        from scraper.sources.api_fetcher import close_shared_client
        await close_shared_client()
        logger.info("Market data HTTP client closed")
    except Exception as e:
        logger.warning(f"Failed to close market data client: {e}")

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
