from datetime import date, datetime
from sqlalchemy import select, func, desc, text
from models.base import async_session
from models.daily_report import DailyReport
from models.trend import Trend
from app.cache import get_cached, set_cached
from fastapi import HTTPException
from app.routes.api_common import router


@router.get("/analysis/daily/{target_date}")
async def get_daily_report(target_date: str):
    """获取每日分析报告"""
    cache_key = f"api:analysis:daily:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        report_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")
    
    async with async_session() as session:
        result = await session.execute(
            select(DailyReport).where(DailyReport.date == report_date)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"未找到 {target_date} 的分析报告")
        
        data = {
            "date": str(report.date),
            "overview": report.overview,
            "hot_topics": report.hot_topics,
            "market_sentiment": report.market_sentiment,
            "key_events": report.key_events,
            "trend_analysis": report.trend_analysis,
            "news_count": report.news_count,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        }
        set_cached(cache_key, data, ttl=600)
        return data


@router.get("/analysis/latest")
async def get_latest_report():
    """获取最新的每日分析报告"""
    cache_key = "api:analysis:latest"
    cached = get_cached(cache_key)
    if cached:
        return cached

    async with async_session() as session:
        result = await session.execute(
            select(DailyReport).order_by(desc(DailyReport.date)).limit(1)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            return {"message": "暂无分析报告"}
        
        data = {
            "date": str(report.date),
            "overview": report.overview,
            "hot_topics": report.hot_topics,
            "market_sentiment": report.market_sentiment,
            "key_events": report.key_events,
            "trend_analysis": report.trend_analysis,
            "news_count": report.news_count,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        }
        set_cached(cache_key, data, ttl=300)
        return data


@router.get("/analysis/sentiment")
async def get_sentiment_stats(target_date: str = None):
    """获取情感分析统计"""
    if target_date:
        try:
            report_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式无效")
    else:
        report_date = date.today()
    
    async with async_session() as session:
        # 统计情感分布
        stmt = text("""
            SELECT 
                ai_sentiment,
                COUNT(*) as count,
                AVG(ai_sentiment_score) as avg_score,
                AVG(ai_importance) as avg_importance
            FROM news
            WHERE DATE(date) = :report_date
              AND ai_sentiment IS NOT NULL
            GROUP BY ai_sentiment
        """)
        result = await session.execute(stmt, {"report_date": report_date})
        sentiments = result.mappings().all()
        
        # 获取重要文章
        stmt_important = text("""
            SELECT id, title, translated_title, ai_sentiment, ai_sentiment_score, 
                   ai_summary_zh, ai_importance, category
            FROM news
            WHERE DATE(date) = :report_date
              AND ai_importance >= 0.7
            ORDER BY ai_importance DESC
            LIMIT 10
        """)
        result_important = await session.execute(stmt_important, {"report_date": report_date})
        important_articles = result_important.mappings().all()
        
        return {
            "date": str(report_date),
            "sentiment_distribution": [
                {
                    "sentiment": row["ai_sentiment"],
                    "count": row["count"],
                    "avg_score": round(float(row["avg_score"]), 2) if row["avg_score"] else 0,
                    "avg_importance": round(float(row["avg_importance"]), 2) if row["avg_importance"] else 0,
                }
                for row in sentiments
            ],
            "important_articles": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "translated_title": row["translated_title"],
                    "sentiment": row["ai_sentiment"],
                    "sentiment_score": round(float(row["ai_sentiment_score"]), 2) if row["ai_sentiment_score"] else 0,
                    "summary_zh": row["ai_summary_zh"],
                    "importance": round(float(row["ai_importance"]), 2) if row["ai_importance"] else 0,
                    "category": row["category"],
                }
                for row in important_articles
            ],
        }


@router.get("/analysis/trends")
async def get_trends(target_date: str = None, keyword: str = None, limit: int = 20):
    """获取趋势数据"""
    cache_key = f"api:analysis:trends:{target_date}:{keyword}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    if target_date:
        try:
            report_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式无效")
    else:
        report_date = date.today()
    
    async with async_session() as session:
        query = select(Trend).where(Trend.date == report_date)
        if keyword:
            query = query.where(Trend.keyword.ilike(f"%{keyword}%"))
        query = query.order_by(desc(Trend.count)).limit(limit)
        
        result = await session.execute(query)
        trends = result.scalars().all()
        
        data = {
            "date": str(report_date),
            "trends": [
                {
                    "keyword": t.keyword,
                    "count": t.count,
                    "sentiment": t.sentiment,
                    "trend": t.trend,
                    "analysis": t.analysis,
                    "related_topics": t.related_topics,
                }
                for t in trends
            ],
        }
        set_cached(cache_key, data, ttl=300)
        return data


@router.get("/analysis/status")
async def get_analysis_status():
    """获取 AI 分析功能状态"""
    from scraper.pipeline.ai_analysis import is_ai_enabled
    
    async with async_session() as session:
        stmt_analyzed = text("SELECT COUNT(*) FROM news WHERE ai_analyzed_at IS NOT NULL")
        stmt_total = text("SELECT COUNT(*) FROM news")
        
        analyzed = (await session.execute(stmt_analyzed)).scalar()
        total = (await session.execute(stmt_total)).scalar()
        
        stmt_latest = text("SELECT MAX(date) FROM daily_reports")
        latest_report = (await session.execute(stmt_latest)).scalar()
        
        return {
            "ai_enabled": is_ai_enabled(),
            "articles_analyzed": analyzed,
            "articles_total": total,
            "analysis_coverage": round(analyzed / total * 100, 1) if total > 0 else 0,
            "latest_report_date": str(latest_report) if latest_report else None,
        }


@router.get("/analysis/weekly/{target_date}")
async def get_weekly_report(target_date: str):
    """获取周报"""
    cache_key = f"api:analysis:weekly:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        report_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")
    
    async with async_session() as session:
        # 计算周范围
        from datetime import timedelta
        weekday = report_date.weekday()
        start_date = report_date - timedelta(days=weekday)
        end_date = start_date + timedelta(days=6)
        
        result = await session.execute(text("""
            SELECT * FROM weekly_reports 
            WHERE period_start = :start_date
        """), {"start_date": start_date})
        report = result.mappings().first()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"未找到 {start_date} 的周报")
        
        data = {
            "period": "weekly",
            "period_start": str(report["period_start"]),
            "period_end": str(report["period_end"]),
            "overview": report["overview"],
            "hot_topics": report["hot_topics"],
            "market_sentiment": report["market_sentiment"],
            "key_events": report["key_events"],
            "trend_analysis": report["trend_analysis"],
            "category_stats": report["category_stats"],
            "sentiment_stats": report["sentiment_stats"],
            "news_count": report["news_count"],
            "generated_at": report["generated_at"].isoformat() if report["generated_at"] else None,
        }
        set_cached(cache_key, data, ttl=600)
        return data


@router.get("/analysis/monthly/{target_date}")
async def get_monthly_report(target_date: str):
    """获取月报"""
    cache_key = f"api:analysis:monthly:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        report_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")
    
    async with async_session() as session:
        # 计算月范围
        start_date = report_date.replace(day=1)
        
        result = await session.execute(text("""
            SELECT * FROM monthly_reports 
            WHERE period_start = :start_date
        """), {"start_date": start_date})
        report = result.mappings().first()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"未找到 {start_date.strftime('%Y-%m')} 的月报")
        
        data = {
            "period": "monthly",
            "period_start": str(report["period_start"]),
            "period_end": str(report["period_end"]),
            "overview": report["overview"],
            "hot_topics": report["hot_topics"],
            "market_sentiment": report["market_sentiment"],
            "key_events": report["key_events"],
            "trend_analysis": report["trend_analysis"],
            "category_stats": report["category_stats"],
            "sentiment_stats": report["sentiment_stats"],
            "news_count": report["news_count"],
            "generated_at": report["generated_at"].isoformat() if report["generated_at"] else None,
        }
        set_cached(cache_key, data, ttl=600)
        return data


@router.get("/analysis/reports")
async def get_reports_list(period: str = "weekly", limit: int = 10):
    """获取报告列表"""
    cache_key = f"api:analysis:reports:{period}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # 使用白名单验证表名，防止 SQL 注入
    ALLOWED_TABLES = {"weekly_reports", "monthly_reports"}
    table_name = "weekly_reports" if period == "weekly" else "monthly_reports"
    
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail="无效的报告类型")
    
    async with async_session() as session:
        result = await session.execute(text(f"""
            SELECT period_start, period_end, overview, market_sentiment, news_count, generated_at
            FROM {table_name}
            ORDER BY period_start DESC
            LIMIT :limit
        """), {"limit": limit})
        
        reports = []
        for row in result.mappings():
            reports.append({
                "period_start": str(row["period_start"]),
                "period_end": str(row["period_end"]),
                "overview": row["overview"][:200] if row["overview"] else "",
                "market_sentiment": row["market_sentiment"],
                "news_count": row["news_count"],
                "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
            })
        
        data = {"period": period, "reports": reports}
        set_cached(cache_key, data, ttl=300)
        return data
