"""
每日分析报告脚本

功能：
1. 分析当日未分析的文章
2. 生成每日综合报告
3. 更新趋势数据

使用方法：
    python scripts/run_daily_analysis.py [--date YYYY-MM-DD] [--analyze-articles] [--generate-report]
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, date, timedelta
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


async def analyze_articles(articles: list[dict], session: AsyncSession) -> int:
    """分析文章并更新数据库"""
    if not is_ai_enabled():
        logger.warning("AI 分析功能未启用，请配置 DEEPSEEK_API_KEY")
        return 0
    
    client = get_ai_client()
    analyzed_count = 0
    
    for article in articles:
        logger.info(f"分析文章: {article['title'][:50]}...")
        
        result = client.analyze_article(
            title=article["title"],
            content=article.get("content"),
            summary=article.get("summary"),
            category=article.get("category"),
            lang=article.get("lang", "en")
        )
        
        if result:
            # 更新数据库
            stmt = (
                update(News)
                .where(News.id == article["id"])
                .values(
                    ai_sentiment=result.sentiment,
                    ai_sentiment_score=result.sentiment_score,
                    ai_summary_zh=result.summary_zh,
                    ai_key_points=result.key_points,
                    ai_tags=result.tags,
                    ai_importance=result.importance,
                    ai_analyzed_at=datetime.now()
                )
            )
            await session.execute(stmt)
            analyzed_count += 1
            
            logger.info(f"  情感: {result.sentiment} ({result.sentiment_score:.2f}), 重要性: {result.importance:.2f}")
        else:
            logger.warning(f"  分析失败")
        
        # 避免 API 速率限制
        await asyncio.sleep(1)
    
    await session.commit()
    return analyzed_count


async def get_articles_for_report(session: AsyncSession, target_date: date = None) -> list[dict]:
    """获取用于生成报告的文章"""
    if target_date is None:
        target_date = date.today()
    
    stmt = (
        select(News)
        .where(func.date(News.date) == target_date)
        .order_by(News.ai_importance.desc().nullslast(), News.created_at.desc())
        .limit(50)
    )
    
    result = await session.execute(stmt)
    articles = []
    
    for row in result.scalars():
        articles.append({
            "id": row.id,
            "title": row.title,
            "summary": row.ai_summary_zh or row.summary,
            "category": row.category,
            "sentiment": row.ai_sentiment,
            "importance": row.ai_importance,
            "date": row.date
        })
    
    return articles


async def generate_daily_report(target_date: date = None) -> bool:
    """生成每日分析报告"""
    if not is_ai_enabled():
        logger.warning("AI 分析功能未启用，请配置 DEEPSEEK_API_KEY")
        return False
    
    if target_date is None:
        target_date = date.today()
    
    client = get_ai_client()
    
    async with async_session() as session:
        # 获取文章
        articles = await get_articles_for_report(session, target_date)
        
        if not articles:
            logger.warning(f"没有找到 {target_date} 的文章")
            return False
        
        logger.info(f"正在生成 {target_date} 的分析报告，共 {len(articles)} 篇文章")
        
        # 生成报告
        report = client.generate_daily_report(articles, target_date)
        
        if not report:
            logger.error("生成报告失败")
            return False
        
        # 保存到数据库
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        
        stmt = """
            INSERT INTO daily_reports (date, overview, hot_topics, market_sentiment, key_events, trend_analysis, news_count)
            VALUES (:date, :overview, :hot_topics, :market_sentiment, :key_events, :trend_analysis, :news_count)
            ON CONFLICT (date) DO UPDATE SET
                overview = EXCLUDED.overview,
                hot_topics = EXCLUDED.hot_topics,
                market_sentiment = EXCLUDED.market_sentiment,
                key_events = EXCLUDED.key_events,
                trend_analysis = EXCLUDED.trend_analysis,
                news_count = EXCLUDED.news_count,
                generated_at = NOW()
        """
        
        import json
        
        await session.execute(stmt, {
            "date": target_date,
            "overview": report.overview,
            "hot_topics": json.dumps(report.hot_topics, ensure_ascii=False),
            "market_sentiment": report.market_sentiment,
            "key_events": json.dumps(report.key_events, ensure_ascii=False),
            "trend_analysis": report.trend_analysis,
            "news_count": report.news_count
        })
        
        await session.commit()
        
        logger.info(f"报告已生成并保存")
        logger.info(f"  概述: {report.overview[:100]}...")
        logger.info(f"  市场情绪: {report.market_sentiment}")
        logger.info(f"  热门话题: {len(report.hot_topics)} 个")
        
        return True


async def run_analysis(target_date: date = None, analyze_articles_flag: bool = True, generate_report_flag: bool = True):
    """运行分析流程"""
    logger.info("=" * 60)
    logger.info("开始每日分析任务")
    logger.info("=" * 60)
    
    if not is_ai_enabled():
        logger.error("AI 分析功能未启用")
        logger.error("请在 .env 文件中配置 DEEPSEEK_API_KEY")
        return
    
    async with async_session() as session:
        # 1. 分析未处理的文章
        if analyze_articles_flag:
            logger.info("\n📊 步骤 1: 分析文章")
            articles = await get_unanalyzed_articles(session, target_date)
            
            if articles:
                logger.info(f"找到 {len(articles)} 篇未分析的文章")
                analyzed = await analyze_articles(articles, session)
                logger.info(f"成功分析 {analyzed} 篇文章")
            else:
                logger.info("没有未分析的文章")
        
        # 2. 生成每日报告
        if generate_report_flag:
            logger.info("\n📈 步骤 2: 生成每日报告")
            success = await generate_daily_report(target_date)
            
            if success:
                logger.info("每日报告生成完成")
            else:
                logger.warning("每日报告生成失败")
    
    logger.info("\n" + "=" * 60)
    logger.info("分析任务完成")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="每日分析报告脚本")
    parser.add_argument("--date", type=str, help="分析日期 (YYYY-MM-DD)，默认今天")
    parser.add_argument("--analyze-articles", action="store_true", default=True, help="分析文章")
    parser.add_argument("--no-analyze-articles", action="store_false", dest="analyze_articles", help="跳过文章分析")
    parser.add_argument("--generate-report", action="store_true", default=True, help="生成每日报告")
    parser.add_argument("--no-generate-report", action="store_false", dest="generate_report", help="跳过报告生成")
    
    args = parser.parse_args()
    
    # 解析日期
    target_date = None
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"无效的日期格式: {args.date}，请使用 YYYY-MM-DD")
            sys.exit(1)
    
    # 运行分析
    asyncio.run(run_analysis(
        target_date=target_date,
        analyze_articles_flag=args.analyze_articles,
        generate_report_flag=args.generate_report
    ))


if __name__ == "__main__":
    main()
