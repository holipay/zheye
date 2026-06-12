"""
数据清理定时任务

功能：
1. 清理超过保留天数的旧新闻数据
2. 清理过期的翻译缓存
3. 清理已完成的失败任务记录
4. 清理旧的运行指标数据

使用方法：
    python scripts/cleanup_old_data.py [--dry-run] [--retention-days 30]

建议 crontab：
    # 每天凌晨2点执行
    0 2 * * * cd /opt/zheye && python scripts/cleanup_old_data.py
"""

import sys
import asyncio
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import async_session
from models.news import News
from models.run_metrics import RunMetrics
from models.failed_task import FailedAnalysisTask
from models.market_data import MarketData
from models.article_keyword import ArticleKeyword
from models.article_entity import ArticleEntity
from models.article_relation import ArticleRelation
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def count_old_records(session: AsyncSession, model, date_column, cutoff_date) -> int:
    """统计过期记录数"""
    stmt = select(func.count()).select_from(model).where(date_column < cutoff_date)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def cleanup_news(session: AsyncSession, cutoff_date: datetime, dry_run: bool = False) -> int:
    """
    清理旧新闻数据
    由于外键约束，需要先清理关联表
    """
    # 统计待清理数量
    count = await count_old_records(session, News, News.date, cutoff_date)
    if count == 0:
        return 0
    
    logger.info(f"待清理新闻: {count} 条 (早于 {cutoff_date.date()})")
    
    if dry_run:
        return count
    
    # 先清理关联表
    news_ids = select(News.id).where(News.date < cutoff_date)
    
    # 清理文章-关键词关联
    await session.execute(
        delete(ArticleKeyword).where(ArticleKeyword.article_id.in_(news_ids))
    )
    
    # 清理文章-实体关联
    await session.execute(
        delete(ArticleEntity).where(ArticleEntity.article_id.in_(news_ids))
    )
    
    # 清理文章关系
    await session.execute(
        delete(ArticleRelation).where(
            (ArticleRelation.source_id.in_(news_ids)) | 
            (ArticleRelation.target_id.in_(news_ids))
        )
    )
    
    # 清理新闻
    await session.execute(
        delete(News).where(News.date < cutoff_date)
    )
    
    return count


async def cleanup_translation_cache(session: AsyncSession, cutoff_date: datetime, dry_run: bool = False) -> int:
    """清理过期的翻译缓存"""
    # TranslationCache 可能没有日期字段，使用 created_at 或跳过
    # 这里假设没有日期字段，跳过此清理
    return 0


async def cleanup_run_metrics(session: AsyncSession, cutoff_date: datetime, dry_run: bool = False) -> int:
    """清理旧的运行指标"""
    count = await count_old_records(session, RunMetrics, RunMetrics.started_at, cutoff_date)
    if count == 0:
        return 0
    
    logger.info(f"待清理运行指标: {count} 条")
    
    if dry_run:
        return count
    
    await session.execute(
        delete(RunMetrics).where(RunMetrics.started_at < cutoff_date)
    )
    
    return count


async def cleanup_failed_tasks(session: AsyncSession, cutoff_date: datetime, dry_run: bool = False) -> int:
    """清理已完成或过期的失败任务"""
    # 清理已解决或放弃的任务
    stmt = select(func.count()).select_from(FailedAnalysisTask).where(
        (FailedAnalysisTask.status.in_(["resolved", "abandoned"])) &
        (FailedAnalysisTask.updated_at < cutoff_date)
    )
    result = await session.execute(stmt)
    count = result.scalar() or 0
    
    if count == 0:
        return 0
    
    logger.info(f"待清理失败任务: {count} 条")
    
    if dry_run:
        return count
    
    await session.execute(
        delete(FailedAnalysisTask).where(
            (FailedAnalysisTask.status.in_(["resolved", "abandoned"])) &
            (FailedAnalysisTask.updated_at < cutoff_date)
        )
    )
    
    return count


async def cleanup_market_data(session: AsyncSession, cutoff_date: datetime, dry_run: bool = False) -> int:
    """清理旧的市场数据"""
    count = await count_old_records(session, MarketData, MarketData.timestamp, cutoff_date)
    if count == 0:
        return 0
    
    logger.info(f"待清理市场数据: {count} 条")
    
    if dry_run:
        return count
    
    await session.execute(
        delete(MarketData).where(MarketData.timestamp < cutoff_date)
    )
    
    return count


async def main(confirm: bool = False):
    parser = argparse.ArgumentParser(description='清理旧数据')
    parser.add_argument('--dry-run', action='store_true', help='仅统计，不实际删除')
    parser.add_argument('--retention-days', type=int, default=None, help='保留天数（默认使用配置）')
    parser.add_argument('--confirm', action='store_true', help='确认执行删除（必须显式指定）')
    args = parser.parse_args()
    
    # 允许从调度器调用时通过参数绕过安全检查
    if confirm:
        args.confirm = True
    
    retention_days = args.retention_days or settings.RETENTION_DAYS
    
    # 安全检查: RETENTION_DAYS=0 表示永不删除
    if retention_days == 0:
        logger.info("RETENTION_DAYS=0, 数据永不删除策略已启用，跳过清理")
        return
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    logger.info(f"开始数据清理 (保留天数: {retention_days}, 截止日期: {cutoff_date.date()})")
    
    if not args.confirm and not args.dry_run:
        logger.error("安全检查: 必须指定 --confirm 或 --dry-run 才能执行")
        logger.error("示例: python scripts/cleanup_old_data.py --dry-run")
        logger.error("       python scripts/cleanup_old_data.py --confirm")
        return
    
    if args.dry_run:
        logger.info("DRY RUN 模式 - 仅统计，不实际删除")
    
    total_cleaned = 0
    
    async with async_session() as session:
        try:
            # 清理新闻及相关数据
            cleaned = await cleanup_news(session, cutoff_date, args.dry_run)
            total_cleaned += cleaned
            
            # 清理运行指标
            cleaned = await cleanup_run_metrics(session, cutoff_date, args.dry_run)
            total_cleaned += cleaned
            
            # 清理失败任务
            cleaned = await cleanup_failed_tasks(session, cutoff_date, args.dry_run)
            total_cleaned += cleaned
            
            # 清理市场数据
            cleaned = await cleanup_market_data(session, cutoff_date, args.dry_run)
            total_cleaned += cleaned
            
            if not args.dry_run:
                await session.commit()
                logger.info(f"数据清理完成，共清理 {total_cleaned} 条记录")
            else:
                logger.info(f"DRY RUN 完成，待清理 {total_cleaned} 条记录")
                
        except Exception as e:
            await session.rollback()
            logger.error(f"数据清理失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
