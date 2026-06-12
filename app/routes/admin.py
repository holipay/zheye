"""
管理后台路由
提供 RSS 源管理、数据监控、系统配置等功能
"""

import os
import asyncio
import yaml
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import get_session
from models.news import News
from models.source_health import SourceHealth
from models.run_metrics import RunMetrics
from models.event import Event
from app.i18n import get_text, DEFAULT_LANGUAGE
from app.auth import verify_admin_credentials, check_admin_enabled
from app.csrf import csrf_protect
from app.context import get_template_context
from app.errors import ErrorMessages as Err

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


class SourceUpdateRequest(BaseModel):
    """RSS 源更新请求模型"""
    weight: Optional[float] = Field(None, ge=0, le=10, description="权重 0-10")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    enabled: Optional[bool] = Field(None, description="是否启用")
    timeout: Optional[int] = Field(None, ge=1, le=120, description="超时时间 1-120 秒")

# RSS 源配置文件路径
CONFIG_PATH = Path(__file__).parent.parent.parent / "scraper" / "sources" / "config.yaml"


def _load_rss_config_sync() -> dict[str, Any]:
    """同步加载 RSS 源配置"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return {"sources": [], "settings": {}}


def _save_rss_config_sync(config: dict[str, Any]) -> bool:
    """同步保存 RSS 源配置"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return False


async def load_rss_config() -> dict[str, Any]:
    """异步加载 RSS 源配置"""
    return await asyncio.to_thread(_load_rss_config_sync)


async def save_rss_config(config: dict[str, Any]) -> bool:
    """异步保存 RSS 源配置"""
    return await asyncio.to_thread(_save_rss_config_sync, config)


# ============================================================
# 管理后台页面
# ============================================================

@router.get("/admin", response_class=HTMLResponse)
async def admin_root(request: Request):
    """管理后台根路径，检查认证后重定向"""
    check_admin_enabled()
    return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/admin")


@router.get("/{lang}/admin", response_class=HTMLResponse)
async def admin_index(request: Request, lang: str, _: bool = Depends(verify_admin_credentials)):
    """管理后台首页"""
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/admin")
    ctx = get_template_context(request, include_csrf=True, title="Dashboard")
    return templates.TemplateResponse(request=request, name="admin/index.html", context=ctx)


@router.get("/{lang}/admin/sources", response_class=HTMLResponse)
async def admin_sources(request: Request, lang: str, _: bool = Depends(verify_admin_credentials)):
    """RSS 源管理页面"""
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/admin/sources")
    ctx = get_template_context(request, include_csrf=True, title="RSS Sources")
    return templates.TemplateResponse(request=request, name="admin/sources.html", context=ctx)


@router.get("/{lang}/admin/monitor", response_class=HTMLResponse)
async def admin_monitor(request: Request, lang: str, _: bool = Depends(verify_admin_credentials)):
    """数据监控页面"""
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/admin/monitor")
    ctx = get_template_context(request, include_csrf=True, title="Data Monitor")
    return templates.TemplateResponse(request=request, name="admin/monitor.html", context=ctx)


@router.get("/{lang}/admin/logs", response_class=HTMLResponse)
async def admin_logs(request: Request, lang: str, _: bool = Depends(verify_admin_credentials)):
    """运行日志页面"""
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/admin/logs")
    ctx = get_template_context(request, include_csrf=True, title="Logs")
    return templates.TemplateResponse(request=request, name="admin/logs.html", context=ctx)


# ============================================================
# API 端点
# ============================================================

@router.get("/admin/api/dashboard")
async def get_dashboard(
    _: bool = Depends(verify_admin_credentials),
    session: AsyncSession = Depends(get_session),
):
    """获取仪表盘数据"""
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    # 使用单条 SQL 获取新闻统计（total, today, week）
    news_stats_result = await session.execute(
        select(
            func.count(News.id).label("total"),
            func.count(News.id).filter(func.date(News.created_at) == today).label("today"),
            func.count(News.id).filter(News.created_at >= week_ago).label("week")
        )
    )
    news_stats = news_stats_result.one()
    total_news = news_stats.total
    today_news = news_stats.today
    week_news = news_stats.week
    
    # 使用单条 SQL 获取源统计（total, healthy）
    source_stats_result = await session.execute(
        select(
            func.count(SourceHealth.id).label("total"),
            func.count(SourceHealth.id).filter(SourceHealth.consecutive_failures < 3).label("healthy")
        )
    )
    source_stats = source_stats_result.one()
    source_count = source_stats.total
    healthy_sources = source_stats.healthy
    
    # 事件统计
    active_events = (await session.execute(
        select(func.count(Event.id)).where(Event.status == "active")
    )).scalar()
    
    # 最近运行记录
    last_run_result = await session.execute(
        select(RunMetrics).order_by(desc(RunMetrics.started_at)).limit(1)
    )
    last_run = last_run_result.scalar_one_or_none()
    
    # 分类统计
    category_stats_result = await session.execute(
        select(News.category, func.count(News.id))
        .group_by(News.category)
        .order_by(desc(func.count(News.id)))
    )
    category_stats = [{"name": row[0], "count": row[1]} for row in category_stats_result.all()]
    
    # 最近7天每日新闻数量 - 使用单条 SQL 按日期分组
    daily_stats_result = await session.execute(
        select(
            func.date(News.date).label("day"),
            func.count(News.id).label("count")
        )
        .where(News.date >= today - timedelta(days=6))
        .group_by(func.date(News.date))
        .order_by(func.date(News.date))
    )
    daily_counts = {str(row.day): row.count for row in daily_stats_result.all()}
    
    # 填充缺失的日期
    daily_stats = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = str(day)
        daily_stats.append({"date": day_str, "count": daily_counts.get(day_str, 0)})
    
    return {
        "overview": {
            "total_news": total_news,
            "today_news": today_news,
            "week_news": week_news,
            "source_count": source_count,
            "healthy_sources": healthy_sources,
            "active_events": active_events,
        },
        "last_run": {
            "run_type": last_run.run_type if last_run else None,
            "started_at": last_run.started_at.isoformat() if last_run and last_run.started_at else None,
            "duration": last_run.duration_seconds if last_run else None,
            "items_fetched": last_run.items_fetched if last_run else 0,
            "items_saved": last_run.items_final if last_run else 0,
        } if last_run else None,
        "category_stats": category_stats,
        "daily_stats": daily_stats,
    }


@router.get("/admin/api/sources")
async def get_sources(
    _: bool = Depends(verify_admin_credentials),
    session: AsyncSession = Depends(get_session),
):
    """获取所有 RSS 源及其健康状态"""
    config = await load_rss_config()
    sources = config.get("sources", [])
    
    # 获取源健康状态
    health_result = await session.execute(select(SourceHealth))
    health_map = {}
    for h in health_result.scalars():
        health_map[h.source_name] = {
            "total_checks": h.total_checks,
            "total_success": h.total_success,
            "total_failure": h.total_failure,
            "consecutive_failures": h.consecutive_failures,
            "last_check": h.last_check.isoformat() if h.last_check else None,
            "last_success": h.last_success.isoformat() if h.last_success else None,
            "last_error": h.last_error,
            "last_items": h.last_items,
            "success_rate": h.success_rate,
        }
    
    # 合并配置和健康状态
    source_list = []
    for src in sources:
        name = src.get("name", "")
        source_list.append({
            "name": name,
            "url": src.get("url", ""),
            "lang": src.get("lang", "en"),
            "category": src.get("category", ""),
            "weight": src.get("weight", 1.0),
            "enabled": src.get("enabled", True),
            "health": health_map.get(name),
        })
    
    return {"sources": source_list, "total": len(source_list)}


@router.get("/admin/api/sources/{source_name}")
async def get_source_detail(
    source_name: str,
    _: bool = Depends(verify_admin_credentials),
    session: AsyncSession = Depends(get_session),
):
    """获取单个源详情"""
    config = await load_rss_config()
    sources = config.get("sources", [])
    
    source = None
    for src in sources:
        if src.get("name") == source_name:
            source = src
            break
    
    if not source:
        raise HTTPException(status_code=404, detail=Err.SOURCE_NOT_FOUND)
    
    # 获取健康状态
    health_result = await session.execute(
        select(SourceHealth).where(SourceHealth.source_name == source_name)
    )
    health = health_result.scalar_one_or_none()
    
    # 获取最近抓取的新闻
    news_result = await session.execute(
        select(News)
        .where(News.source == source_name)
        .order_by(desc(News.created_at))
        .limit(10)
    )
    recent_news = []
    for n in news_result.scalars():
        recent_news.append({
            "id": n.id,
            "title": n.title,
            "date": n.date.isoformat() if n.date else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        })
    
    return {
        "source": source,
        "health": {
            "total_checks": health.total_checks if health else 0,
            "total_success": health.total_success if health else 0,
            "total_failure": health.total_failure if health else 0,
            "consecutive_failures": health.consecutive_failures if health else 0,
            "last_check": health.last_check.isoformat() if health and health.last_check else None,
            "last_success": health.last_success.isoformat() if health and health.last_success else None,
            "last_error": health.last_error if health else None,
            "last_items": health.last_items if health else 0,
            "success_rate": health.success_rate if health else 0,
        },
        "recent_news": recent_news,
    }


@router.post("/admin/api/sources/{source_name}/toggle")
async def toggle_source(source_name: str, request: Request, _: bool = Depends(verify_admin_credentials), __: bool = Depends(csrf_protect)):
    """启用/禁用源"""
    config = await load_rss_config()
    sources = config.get("sources", [])
    
    found = False
    for src in sources:
        if src.get("name") == source_name:
            src["enabled"] = not src.get("enabled", True)
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail=Err.SOURCE_NOT_FOUND)
    
    if await save_rss_config(config):
        return {"success": True, "message": f"源 {source_name} 状态已更新"}
    else:
        raise HTTPException(status_code=500, detail=Err.SAVE_CONFIG_FAILED)


@router.put("/admin/api/sources/{source_name}")
async def update_source(
    source_name: str,
    data: SourceUpdateRequest,
    _: bool = Depends(verify_admin_credentials),
    __: bool = Depends(csrf_protect),
):
    """更新源配置"""
    config = await load_rss_config()
    sources = config.get("sources", [])
    
    found = False
    for src in sources:
        if src.get("name") == source_name:
            if data.weight is not None:
                src["weight"] = data.weight
            if data.category is not None:
                src["category"] = data.category
            if data.enabled is not None:
                src["enabled"] = data.enabled
            if data.timeout is not None:
                src["timeout"] = data.timeout
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail=Err.SOURCE_NOT_FOUND)
    
    if await save_rss_config(config):
        return {"success": True, "message": f"源 {source_name} 配置已更新"}
    else:
        raise HTTPException(status_code=500, detail=Err.SAVE_CONFIG_FAILED)


@router.get("/admin/api/run-history")
async def get_run_history(
    limit: int = Query(default=20, le=100),
    _: bool = Depends(verify_admin_credentials),
    session: AsyncSession = Depends(get_session),
):
    """获取运行历史"""
    result = await session.execute(
        select(RunMetrics)
        .order_by(desc(RunMetrics.started_at))
        .limit(limit)
    )
    
    runs = []
    for run in result.scalars():
        runs.append({
            "id": run.id,
            "run_type": run.run_type,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "duration": run.duration_seconds,
            "sources_attempted": run.sources_attempted,
            "sources_succeeded": run.sources_succeeded,
            "sources_failed": run.sources_failed,
            "items_fetched": run.items_fetched,
            "items_deduped": run.items_deduped,
            "items_final": run.items_final,
        })
    
    return {"runs": runs, "total": len(runs)}


@router.get("/admin/api/source-stats")
async def get_source_stats(
    _: bool = Depends(verify_admin_credentials),
    session: AsyncSession = Depends(get_session),
):
    """获取源统计信息"""
    # 按源统计新闻数量
    result = await session.execute(
        select(News.source, func.count(News.id))
        .group_by(News.source)
        .order_by(desc(func.count(News.id)))
        .limit(20)
    )
    
    stats = [{"source": row[0], "count": row[1]} for row in result.all()]
    
    return {"stats": stats}


@router.get("/admin/api/system-info")
async def get_system_info(_: bool = Depends(verify_admin_credentials)):
    """获取系统信息"""
    import platform
    import sys
    
    # 数据库连接信息脱敏：只显示是否配置，不暴露主机信息
    db_configured = bool(os.getenv("DATABASE_URL"))
    
    return {
        "platform": platform.platform(),
        "python_version": sys.version,
        "database_configured": db_configured,
        "ai_enabled": bool(os.getenv("DEEPSEEK_API_KEY")),
        "config_path": str(CONFIG_PATH.name),  # 只返回文件名，不返回完整路径
        "config_exists": CONFIG_PATH.exists(),
    }
