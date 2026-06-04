from datetime import date, datetime
from sqlalchemy import select, func, desc, text, Table, Column, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_session
from models.daily_report import DailyReport
from models.trend import Trend
from models.failed_task import FailedAnalysisTask
from models.analysis_version import AnalysisVersion
from app.cache import get_cached, set_cached
from fastapi import HTTPException, Depends, Query
from app.routes.api_common import router

REPORT_TABLES = {"weekly_reports", "monthly_reports"}


def parse_date(target_date: str) -> date:
    """
    解析日期字符串
    
    Args:
        target_date: 日期字符串 (YYYY-MM-DD)
    
    Returns:
        date 对象
    
    Raises:
        HTTPException: 日期格式无效
    """
    try:
        return date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")


def serialize_daily_report(report: DailyReport) -> dict:
    """
    序列化每日报告
    
    Args:
        report: DailyReport 对象
    
    Returns:
        序列化后的字典
    """
    return {
        "date": str(report.date),
        "overview": report.overview,
        "hot_topics": report.hot_topics,
        "market_sentiment": report.market_sentiment,
        "key_events": report.key_events,
        "trend_analysis": report.trend_analysis,
        "news_count": report.news_count,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }


@router.get("/analysis/daily/{target_date}")
async def get_daily_report(
    target_date: str,
    session: AsyncSession = Depends(get_session),
):
    """获取每日分析报告"""
    cache_key = f"api:analysis:daily:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    report_date = parse_date(target_date)
    
    result = await session.execute(
        select(DailyReport).where(DailyReport.date == report_date)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail=f"未找到 {target_date} 的分析报告")
    
    data = serialize_daily_report(report)
    set_cached(cache_key, data, ttl=600)
    return data


@router.get("/analysis/latest")
async def get_latest_report(session: AsyncSession = Depends(get_session)):
    """获取最新的每日分析报告"""
    cache_key = "api:analysis:latest"
    cached = get_cached(cache_key)
    if cached:
        return cached

    result = await session.execute(
        select(DailyReport).order_by(desc(DailyReport.date)).limit(1)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        return {"message": "暂无分析报告"}
    
    data = serialize_daily_report(report)
    set_cached(cache_key, data, ttl=300)
    return data


@router.get("/analysis/sentiment")
async def get_sentiment_stats(
    session: AsyncSession = Depends(get_session),
    target_date: str = None,
):
    """获取情感分析统计"""
    report_date = parse_date(target_date) if target_date else date.today()
    
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
async def get_trends(
    session: AsyncSession = Depends(get_session),
    target_date: str = None,
    keyword: str = None,
    limit: int = 20,
):
    """获取趋势数据"""
    cache_key = f"api:analysis:trends:{target_date}:{keyword}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    report_date = parse_date(target_date) if target_date else date.today()
    
    query = select(Trend).where(Trend.date == report_date)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Trend.keyword.ilike(f"%{escaped}%"))
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
async def get_analysis_status(session: AsyncSession = Depends(get_session)):
    """获取 AI 分析功能状态"""
    from scraper.pipeline.ai_analysis import is_ai_enabled
    
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
async def get_weekly_report(
    target_date: str,
    session: AsyncSession = Depends(get_session),
):
    """获取周报"""
    cache_key = f"api:analysis:weekly:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    report_date = parse_date(target_date)
    
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
async def get_monthly_report(
    target_date: str,
    session: AsyncSession = Depends(get_session),
):
    """获取月报"""
    cache_key = f"api:analysis:monthly:{target_date}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    report_date = parse_date(target_date)
    
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
async def get_reports_list(
    session: AsyncSession = Depends(get_session),
    period: str = "weekly",
    limit: int = 10,
):
    """获取报告列表"""
    cache_key = f"api:analysis:reports:{period}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # 使用白名单验证表名，防止 SQL 注入
    if period not in REPORT_TABLES:
        raise HTTPException(status_code=400, detail="无效的报告类型")
    
    table_name = REPORT_TABLES[period]
    
    # 使用 SQLAlchemy table 构造替代 f-string SQL 拼接
    metadata = MetaData()
    report_table = Table(
        table_name, metadata,
        Column("period_start"),
        Column("period_end"),
        Column("overview"),
        Column("market_sentiment"),
        Column("news_count"),
        Column("generated_at"),
        extend_existing=True
    )
    
    query = (
        select(
            report_table.c.period_start,
            report_table.c.period_end,
            report_table.c.overview,
            report_table.c.market_sentiment,
            report_table.c.news_count,
            report_table.c.generated_at,
        )
        .order_by(report_table.c.period_start.desc())
        .limit(limit)
    )
    
    result = await session.execute(query)
    
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


# ============================================================
# 失败任务管理 API
# ============================================================

@router.get("/analysis/failed-tasks")
async def get_failed_tasks(
    session: AsyncSession = Depends(get_session),
    task_type: str = None,
    status: str = None,
    limit: int = Query(default=50, le=200),
):
    """获取失败的分析任务列表"""
    query = select(FailedAnalysisTask)
    
    if task_type:
        query = query.where(FailedAnalysisTask.task_type == task_type)
    if status:
        query = query.where(FailedAnalysisTask.status == status)
    
    query = query.order_by(FailedAnalysisTask.created_at.desc()).limit(limit)
    
    result = await session.execute(query)
    tasks = result.scalars().all()
    
    return {
        "tasks": [
            {
                "id": task.id,
                "task_type": task.task_type,
                "target_id": task.target_id,
                "target_type": task.target_type,
                "failure_reason": task.failure_reason,
                "error_message": task.error_message,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "status": task.status,
                "next_retry_at": task.next_retry_at.isoformat() if task.next_retry_at else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            }
            for task in tasks
        ],
        "total": len(tasks),
    }


@router.get("/analysis/failed-tasks/stats")
async def get_failed_tasks_stats(session: AsyncSession = Depends(get_session)):
    """获取失败任务统计信息"""
    from scraper.pipeline.retry_manager import get_retry_manager
    
    manager = get_retry_manager()
    stats = await manager.get_statistics()
    return stats


@router.post("/analysis/failed-tasks/{task_id}/retry")
async def retry_failed_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """手动重试指定的失败任务"""
    from scraper.pipeline.retry_manager import get_retry_manager
    
    manager = get_retry_manager()
    task = await manager.get_task_by_id(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status not in ("pending", "retrying", "abandoned"):
        raise HTTPException(status_code=400, detail=f"任务状态 {task.status} 不可重试")
    
    # 重置任务状态
    await manager.update_task_status(task_id, "pending")
    
    return {
        "message": "任务已重置为待重试状态",
        "task_id": task_id,
        "status": "pending",
    }


@router.post("/analysis/failed-tasks/retry-all")
async def retry_all_failed_tasks(
    session: AsyncSession = Depends(get_session),
    task_type: str = None,
):
    """批量重试所有待重试的失败任务"""
    from scraper.pipeline.retry_manager import get_retry_manager
    
    manager = get_retry_manager()
    
    # 获取所有可重试的任务
    query = select(FailedAnalysisTask).where(
        FailedAnalysisTask.status.in_(["pending", "retrying", "abandoned"])
    )
    if task_type:
        query = query.where(FailedAnalysisTask.task_type == task_type)
    
    result = await session.execute(query)
    tasks = result.scalars().all()
    
    reset_count = 0
    for task in tasks:
        if task.retry_count < task.max_retries:
            await manager.update_task_status(task.id, "pending")
            reset_count += 1
    
    return {
        "message": f"已重置 {reset_count} 个任务",
        "total_tasks": len(tasks),
        "reset_count": reset_count,
    }


@router.delete("/analysis/failed-tasks/{task_id}")
async def delete_failed_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """删除指定的失败任务"""
    task = await session.get(FailedAnalysisTask, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    await session.delete(task)
    await session.commit()
    
    return {"message": "任务已删除", "task_id": task_id}


@router.delete("/analysis/failed-tasks/cleanup")
async def cleanup_failed_tasks(
    session: AsyncSession = Depends(get_session),
    days: int = Query(default=30, ge=1, le=365),
):
    """清理旧的已完成/已放弃任务"""
    from scraper.pipeline.retry_manager import get_retry_manager
    
    manager = get_retry_manager()
    deleted_count = await manager.cleanup_old_tasks(days)
    
    return {
        "message": f"已清理 {deleted_count} 个旧任务",
        "deleted_count": deleted_count,
    }


# ============================================================
# 分析版本管理 API
# ============================================================

@router.get("/analysis/versions/{analysis_type}/{target_id}")
async def get_analysis_versions(
    analysis_type: str,
    target_id: str,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=10, le=50),
):
    """获取分析结果的版本历史"""
    query = (
        select(AnalysisVersion)
        .where(
            AnalysisVersion.analysis_type == analysis_type,
            AnalysisVersion.target_id == target_id,
        )
        .order_by(AnalysisVersion.version_number.desc())
        .limit(limit)
    )
    
    result = await session.execute(query)
    versions = result.scalars().all()
    
    return {
        "analysis_type": analysis_type,
        "target_id": target_id,
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "confidence": v.confidence,
                "change_summary": v.change_summary,
                "changed_fields": v.changed_fields,
                "ai_model": v.ai_model,
                "analysis_duration_ms": v.analysis_duration_ms,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
        "total": len(versions),
    }


@router.get("/analysis/versions/{analysis_type}/{target_id}/compare")
async def compare_analysis_versions(
    analysis_type: str,
    target_id: str,
    version1: int = Query(..., description="第一个版本号"),
    version2: int = Query(..., description="第二个版本号"),
    session: AsyncSession = Depends(get_session),
):
    """对比两个分析版本的差异"""
    # 获取两个版本
    query1 = select(AnalysisVersion).where(
        AnalysisVersion.analysis_type == analysis_type,
        AnalysisVersion.target_id == target_id,
        AnalysisVersion.version_number == version1,
    )
    query2 = select(AnalysisVersion).where(
        AnalysisVersion.analysis_type == analysis_type,
        AnalysisVersion.target_id == target_id,
        AnalysisVersion.version_number == version2,
    )
    
    result1 = await session.execute(query1)
    result2 = await session.execute(query2)
    
    v1 = result1.scalar_one_or_none()
    v2 = result2.scalar_one_or_none()
    
    if not v1:
        raise HTTPException(status_code=404, detail=f"版本 {version1} 不存在")
    if not v2:
        raise HTTPException(status_code=404, detail=f"版本 {version2} 不存在")
    
    # 计算差异
    diff = v1.diff_with(v2)
    
    return {
        "analysis_type": analysis_type,
        "target_id": target_id,
        "version1": {
            "version_number": v1.version_number,
            "confidence": v1.confidence,
            "created_at": v1.created_at.isoformat() if v1.created_at else None,
        },
        "version2": {
            "version_number": v2.version_number,
            "confidence": v2.confidence,
            "created_at": v2.created_at.isoformat() if v2.created_at else None,
        },
        "changes": diff,
        "changed_fields": list(diff.keys()),
        "total_changes": len(diff),
    }


@router.get("/analysis/versions/{analysis_type}/{target_id}/latest")
async def get_latest_version(
    analysis_type: str,
    target_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取最新的分析版本"""
    query = (
        select(AnalysisVersion)
        .where(
            AnalysisVersion.analysis_type == analysis_type,
            AnalysisVersion.target_id == target_id,
        )
        .order_by(AnalysisVersion.version_number.desc())
        .limit(1)
    )
    
    result = await session.execute(query)
    version = result.scalar_one_or_none()
    
    if not version:
        raise HTTPException(status_code=404, detail="未找到分析版本")
    
    return {
        "id": version.id,
        "analysis_type": version.analysis_type,
        "target_id": version.target_id,
        "version_number": version.version_number,
        "result_data": version.result_data,
        "confidence": version.confidence,
        "change_summary": version.change_summary,
        "changed_fields": version.changed_fields,
        "ai_model": version.ai_model,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
