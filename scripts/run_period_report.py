"""
周报/月报分析脚本

功能：
1. 按周或月汇总新闻数据
2. 生成周度/月度分析报告
3. 更新趋势数据

使用方法：
    python scripts/run_period_report.py --period weekly [--date 2026-06-01]
    python scripts/run_period_report.py --period monthly [--date 2026-06-01]
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, func, text
from models.base import async_session
from models.news import News
from scraper.pipeline.ai_analysis import get_ai_client, is_ai_enabled

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_period_range(target_date: date, period: str) -> tuple[date, date]:
    """获取周期范围"""
    if period == "weekly":
        # 获取目标日期所在周的周一和周日
        weekday = target_date.weekday()
        start_date = target_date - timedelta(days=weekday)
        end_date = start_date + timedelta(days=6)
    elif period == "monthly":
        # 获取目标日期所在月的第一天和最后一天
        start_date = target_date.replace(day=1)
        if target_date.month == 12:
            end_date = target_date.replace(year=target_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = target_date.replace(month=target_date.month + 1, day=1) - timedelta(days=1)
    else:
        start_date = target_date
        end_date = target_date
    
    return start_date, end_date


async def get_articles_for_period(session, start_date: date, end_date: date, limit: int = 200) -> list[dict]:
    """获取指定时间段的文章"""
    stmt = (
        select(News)
        .where(
            func.date(News.date) >= start_date,
            func.date(News.date) <= end_date
        )
        .order_by(News.ai_importance.desc().nullslast(), News.date.desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    articles = []
    
    for row in result.scalars():
        articles.append({
            "id": row.id,
            "title": row.title,
            "translated_title": row.translated_title,
            "summary": row.ai_summary_zh or row.summary,
            "category": row.category,
            "source": row.source,
            "lang": row.lang,
            "sentiment": row.ai_sentiment,
            "sentiment_score": row.ai_sentiment_score,
            "importance": row.ai_importance,
            "date": row.date
        })
    
    return articles


async def get_category_stats(session, start_date: date, end_date: date) -> list[dict]:
    """获取分类统计"""
    stmt = (
        select(
            News.category,
            func.count(News.id).label("count"),
            func.avg(News.ai_sentiment_score).label("avg_sentiment"),
            func.avg(News.ai_importance).label("avg_importance")
        )
        .where(
            func.date(News.date) >= start_date,
            func.date(News.date) <= end_date
        )
        .group_by(News.category)
        .order_by(func.count(News.id).desc())
    )
    
    result = await session.execute(stmt)
    stats = []
    
    for row in result:
        stats.append({
            "category": row.category,
            "count": row.count,
            "avg_sentiment": round(float(row.avg_sentiment), 2) if row.avg_sentiment else 0,
            "avg_importance": round(float(row.avg_importance), 2) if row.avg_importance else 0
        })
    
    return stats


async def get_sentiment_distribution(session, start_date: date, end_date: date) -> dict:
    """获取情感分布"""
    stmt = (
        select(
            News.ai_sentiment,
            func.count(News.id).label("count")
        )
        .where(
            func.date(News.date) >= start_date,
            func.date(News.date) <= end_date,
            News.ai_sentiment.isnot(None)
        )
        .group_by(News.ai_sentiment)
    )
    
    result = await session.execute(stmt)
    distribution = {}
    
    for row in result:
        distribution[row.ai_sentiment] = row.count
    
    return distribution


REPORT_TABLES = {"weekly_reports", "monthly_reports"}


async def generate_period_report(target_date: date, period: str) -> bool:
    """生成周期报告"""
    if not is_ai_enabled():
        logger.warning("AI 分析功能未启用，请配置 DEEPSEEK_API_KEY")
        return False
    
    client = get_ai_client()
    start_date, end_date = get_period_range(target_date, period)
    
    async with async_session() as session:
        # 获取文章
        articles = await get_articles_for_period(session, start_date, end_date)
        
        if not articles:
            logger.warning(f"没有找到 {start_date} 到 {end_date} 的文章")
            return False
        
        # 获取统计信息
        category_stats = await get_category_stats(session, start_date, end_date)
        sentiment_dist = await get_sentiment_distribution(session, start_date, end_date)
        
        logger.info(f"正在生成 {period} 报告: {start_date} ~ {end_date}")
        logger.info(f"  文章数量: {len(articles)}")
        logger.info(f"  分类统计: {len(category_stats)} 个分类")
        
        # 构建统计摘要
        stats_summary = {
            "period": period,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "total_articles": len(articles),
            "category_stats": category_stats,
            "sentiment_distribution": sentiment_dist,
            "top_articles": articles[:10]  # 最重要的10篇文章
        }
        
        # 生成报告
        report = client.generate_period_report(articles, stats_summary, period)
        
        if not report:
            logger.error("生成报告失败")
            return False
        
        # 保存到数据库
        table_name = "weekly_reports" if period == "weekly" else "monthly_reports"
        
        # 白名单验证表名，防止 SQL 注入
        if table_name not in REPORT_TABLES:
            logger.error(f"无效的报告类型: {period}")
            return False
        
        # 检查表是否存在，如果不存在则创建
        await ensure_report_tables(session, table_name)
        
        # 保存报告
        import json
        
        stmt = f"""
            INSERT INTO {table_name} (period_start, period_end, overview, hot_topics, market_sentiment, 
                                      key_events, trend_analysis, category_stats, sentiment_stats, news_count)
            VALUES (:period_start, :period_end, :overview, :hot_topics, :market_sentiment, 
                    :key_events, :trend_analysis, :category_stats, :sentiment_stats, :news_count)
            ON CONFLICT (period_start) DO UPDATE SET
                period_end = EXCLUDED.period_end,
                overview = EXCLUDED.overview,
                hot_topics = EXCLUDED.hot_topics,
                market_sentiment = EXCLUDED.market_sentiment,
                key_events = EXCLUDED.key_events,
                trend_analysis = EXCLUDED.trend_analysis,
                category_stats = EXCLUDED.category_stats,
                sentiment_stats = EXCLUDED.sentiment_stats,
                news_count = EXCLUDED.news_count,
                generated_at = NOW()
        """
        
        await session.execute(stmt, {
            "period_start": start_date,
            "period_end": end_date,
            "overview": report.get("overview", ""),
            "hot_topics": json.dumps(report.get("hot_topics", []), ensure_ascii=False),
            "market_sentiment": report.get("market_sentiment", "neutral"),
            "key_events": json.dumps(report.get("key_events", []), ensure_ascii=False),
            "trend_analysis": report.get("trend_analysis", ""),
            "category_stats": json.dumps(category_stats, ensure_ascii=False),
            "sentiment_stats": json.dumps(sentiment_dist, ensure_ascii=False),
            "news_count": len(articles)
        })
        
        await session.commit()
        
        logger.info(f"报告已生成并保存")
        logger.info(f"  概述: {report.get('overview', '')[:100]}...")
        logger.info(f"  市场情绪: {report.get('market_sentiment', '')}")
        
        return True


async def ensure_report_tables(session, table_name: str):
    """确保报告表存在"""
    # 白名单验证表名，防止 SQL 注入
    if table_name not in REPORT_TABLES:
        raise ValueError(f"无效的表名: {table_name}")
    
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGSERIAL PRIMARY KEY,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            overview TEXT,
            hot_topics JSONB,
            market_sentiment VARCHAR(50),
            key_events JSONB,
            trend_analysis TEXT,
            category_stats JSONB,
            sentiment_stats JSONB,
            news_count INT DEFAULT 0,
            generated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(period_start)
        );
        
        CREATE INDEX IF NOT EXISTS idx_{table_name}_period ON {table_name} (period_start DESC);
    """
    
    await session.execute(text(create_table_sql))
    await session.commit()


def main():
    parser = argparse.ArgumentParser(description="周报/月报分析脚本")
    parser.add_argument("--period", choices=["weekly", "monthly"], required=True, help="报告周期")
    parser.add_argument("--date", type=str, help="目标日期 (YYYY-MM-DD)，默认今天")
    
    args = parser.parse_args()
    
    # 解析日期
    target_date = date.today()
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"无效的日期格式: {args.date}，请使用 YYYY-MM-DD")
            sys.exit(1)
    
    # 运行分析
    asyncio.run(generate_period_report(target_date, args.period))


if __name__ == "__main__":
    main()
