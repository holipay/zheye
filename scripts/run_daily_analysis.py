"""
文章分析脚本

功能：
1. 分析当日未分析的文章
2. 更新趋势数据

使用方法：
    python scripts/run_daily_analysis.py [--date YYYY-MM-DD]
"""

import sys
import asyncio
import argparse
import logging
from datetime import datetime, date
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import async_session
from models.news import News
from scraper.pipeline.ai_analysis import get_ai_client, is_ai_enabled

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_unanalyzed_articles(session: AsyncSession, target_date: date = None, limit: int = 100) -> list[dict]:
    """获取未分析的文章"""
    if target_date is None:
        target_date = date.today()
    
    # 查询当天未分析的文章
    stmt = (
        select(News)
        .where(
            func.date(News.date) == target_date,
            News.ai_analyzed_at.is_(None)
        )
        .order_by(News.created_at.desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    articles = []
    
    for row in result.scalars():
        articles.append({
            "id": row.id,
            "title": row.title,
            "translated_title": row.translated_title,
            "summary": row.summary,
            "content": row.content,
            "category": row.category,
            "lang": row.lang,
            "source": row.source,
            "date": row.date
        })
    
    return articles


BATCH_SIZE = 5


async def analyze_articles(articles: list[dict], session: AsyncSession) -> int:
    """批量分析文章并更新数据库（每 BATCH_SIZE 篇一次 API 调用）"""
    if not is_ai_enabled():
        logger.warning("AI 分析功能未启用，请配置 DEEPSEEK_API_KEY")
        return 0

    client = get_ai_client()
    analyzed_count = 0

    for batch_start in range(0, len(articles), BATCH_SIZE):
        batch = articles[batch_start:batch_start + BATCH_SIZE]
        batch_input = [
            {
                "title": art["title"],
                "content": art.get("content"),
                "summary": art.get("summary"),
                "category": art.get("category"),
                "lang": art.get("lang", "en"),
            }
            for art in batch
        ]

        logger.info(f"批量分析 {len(batch)} 篇文章 (#{batch_start}-{batch_start + len(batch) - 1})")

        results = await client.analyze_articles_batch(batch_input)

        for i, art in enumerate(batch):
            result = results.get(i)
            if result:
                stmt = (
                    update(News)
                    .where(News.id == art["id"])
                    .values(
                        ai_sentiment=result.sentiment,
                        ai_sentiment_score=result.sentiment_score,
                        ai_summary_zh=result.summary_zh,
                        ai_importance=result.importance,
                        ai_analyzed_at=datetime.now(),
                    )
                )
                await session.execute(stmt)
                analyzed_count += 1
                logger.info(f"  [{i}] {art['title'][:40]}... -> {result.sentiment} ({result.sentiment_score:.2f})")
            else:
                logger.warning(f"  [{i}] {art['title'][:40]}... 分析失败")

        # 批次间间隔，避免 API 速率限制
        await asyncio.sleep(2)

    await session.commit()
    return analyzed_count


async def run_analysis(target_date: date = None):
    """运行分析流程"""
    logger.info("=" * 60)
    logger.info("开始文章分析任务")
    logger.info("=" * 60)
    
    if not is_ai_enabled():
        logger.error("AI 分析功能未启用")
        logger.error("请在 .env 文件中配置 DEEPSEEK_API_KEY")
        return
    
    async with async_session() as session:
        try:
            # 分析未处理的文章
            logger.info("\n📊 分析文章")
            articles = await get_unanalyzed_articles(session, target_date)
            
            if articles:
                logger.info(f"找到 {len(articles)} 篇未分析的文章")
                analyzed = await analyze_articles(articles, session)
                logger.info(f"成功分析 {analyzed} 篇文章")
            else:
                logger.info("没有未分析的文章")
        except Exception as e:
            await session.rollback()
            logger.error(f"分析失败: {e}")
            raise
    
    logger.info("\n" + "=" * 60)
    logger.info("分析任务完成")
    logger.info("=" * 60)


async def main():
    """入口（async，兼容 lifespan await 调用）"""
    parser = argparse.ArgumentParser(description="文章分析脚本")
    parser.add_argument("--date", type=str, help="分析日期 (YYYY-MM-DD)，默认今天")

    args = parser.parse_args()

    target_date = None
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"无效的日期格式: {args.date}，请使用 YYYY-MM-DD")
            sys.exit(1)

    await run_analysis(target_date=target_date)


if __name__ == "__main__":
    asyncio.run(main())
