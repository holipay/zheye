from datetime import date, datetime, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_session
from models.event import Event
from app.cache import get_cached, set_cached
from fastapi import Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from app.routes.api_common import router, templates, _get_api_context


# ============================================================
# 事件追踪 API
# ============================================================

@router.get("/events")
async def get_events(
    session: AsyncSession = Depends(get_session),
    category: str = None,
    status: str = "active",
    page: int = 1,
    page_size: int = 20,
):
    """获取事件列表"""
    cache_key = f"api:events:{category}:{status}:{page}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    offset = (page - 1) * page_size

    query = select(Event)
    count_query = select(func.count(Event.id))

    if category:
        query = query.where(Event.category == category)
        count_query = count_query.where(Event.category == category)
    if status:
        query = query.where(Event.status == status)
        count_query = count_query.where(Event.status == status)

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(desc(Event.last_updated)).offset(offset).limit(page_size)
    result = await session.execute(query)
    events = result.scalars().all()

    event_list = []
    for event in events:
        event_list.append({
            "id": event.id,
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "category": event.category,
            "first_seen": str(event.first_seen) if event.first_seen else None,
            "last_updated": str(event.last_updated) if event.last_updated else None,
            "update_count": event.update_count,
            "status": event.status,
            "article_count": len(event.related_articles) if event.related_articles else 0,
        })

    total_pages = (total + page_size - 1) // page_size

    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "events": event_list,
    }
    set_cached(cache_key, data, ttl=120)
    return data


@router.get("/events/timeline", response_class=HTMLResponse)
async def get_events_timeline(
    request: Request,
    session: AsyncSession = Depends(get_session),
    category: str = None,
    days: int = 7,
    limit: int = 20,
):
    """获取事件时间线（HTML）"""
    lang = request.query_params.get("lang", "en")
    cache_key = f"api:events:timeline:{lang}:{category}:{days}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    cutoff_date = date.today() - timedelta(days=days)

    query = select(Event).where(Event.last_updated >= cutoff_date)
    if category:
        query = query.where(Event.category == category)
    query = query.order_by(desc(Event.last_updated)).limit(limit)

    result = await session.execute(query)
    events = result.scalars().all()

    event_list = []
    for event in events:
        event_list.append({
            "event_id": event.event_id,
            "title": event.title,
            "category": event.category,
            "first_seen": str(event.first_seen) if event.first_seen else None,
            "last_updated": str(event.last_updated) if event.last_updated else None,
            "update_count": event.update_count,
            "status": event.status,
            "article_count": len(event.related_articles) if event.related_articles else 0,
        })

    response = templates.TemplateResponse(request=request, name="partials/events_timeline.html", context=_get_api_context(
        request, events=event_list, category=category, days=days,
    ))
    set_cached(cache_key, response.body.decode(), ttl=120)
    return response


@router.get("/events/categories")
async def get_event_categories(session: AsyncSession = Depends(get_session)):
    """获取事件分类统计"""
    cache_key = "api:events:categories"
    cached = get_cached(cache_key)
    if cached:
        return cached

    query = (
        select(Event.category, func.count(Event.id))
        .where(Event.status == "active")
        .group_by(Event.category)
        .order_by(desc(func.count(Event.id)))
    )
    result = await session.execute(query)
    categories = [{"name": row[0], "count": row[1]} for row in result.all()]

    data = {"categories": categories}
    set_cached(cache_key, data, ttl=300)
    return data


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取事件详情和时间线"""
    cache_key = f"api:events:detail:{event_id}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    result = await session.execute(
        select(Event).where(Event.event_id == event_id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="事件未找到")

    # 获取关联文章详情
    articles = []
    if event.related_articles:
        for article_ref in event.related_articles[:10]:
            if isinstance(article_ref, dict):
                articles.append(article_ref)

    # 获取事件类型的其他事件（相关事件）
    related_events = []
    if event.data and event.data.get("event_type"):
        event_type = event.data["event_type"]
        related_result = await session.execute(
            select(Event)
            .where(Event.data["event_type"].as_string() == event_type)
            .where(Event.event_id != event_id)
            .order_by(desc(Event.last_updated))
            .limit(5)
        )
        for related in related_result.scalars().all():
            related_events.append({
                "event_id": related.event_id,
                "title": related.title,
                "category": related.category,
                "last_updated": str(related.last_updated) if related.last_updated else None,
                "update_count": related.update_count,
            })

    data = {
        "event_id": event.event_id,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "first_seen": str(event.first_seen) if event.first_seen else None,
        "last_updated": str(event.last_updated) if event.last_updated else None,
        "update_count": event.update_count,
        "status": event.status,
        "event_type": event.data.get("event_type") if event.data else None,
        "timeline": articles,
        "related_events": related_events,
    }
    set_cached(cache_key, data, ttl=300)
    return data
