from datetime import date, datetime, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_session
from models.event import Event
from deep_analyst.models.causal_chain import CausalNode, CausalLink, NodeType
from app.cache import get_cached, set_cached
from app.errors import ErrorMessages as Err
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
        raise HTTPException(status_code=404, detail=Err.EVENT_NOT_FOUND)

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

    # 获取因果链数据
    causal_chain = await _get_causal_chain(session, event_id)

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
        "causal_chain": causal_chain,
    }
    set_cached(cache_key, data, ttl=300)
    return data


async def _get_causal_chain(session: AsyncSession, event_id: str) -> dict:
    """
    获取事件的因果链数据
    
    Args:
        session: 数据库会话
        event_id: 事件ID
    
    Returns:
        因果链数据字典，包含nodes和links
    """
    # 查询因果节点
    nodes_query = (
        select(CausalNode)
        .where(CausalNode.event_id == event_id)
        .order_by(CausalNode.created_at)
    )
    nodes_result = await session.execute(nodes_query)
    nodes = nodes_result.scalars().all()
    
    if not nodes:
        return {"nodes": [], "links": [], "mermaid": ""}
    
    # 查询因果关系
    node_ids = [node.id for node in nodes]
    links_query = (
        select(CausalLink)
        .where(
            CausalLink.source_node_id.in_(node_ids),
            CausalLink.target_node_id.in_(node_ids)
        )
    )
    links_result = await session.execute(links_query)
    links = links_result.scalars().all()
    
    # 构建节点数据
    nodes_data = []
    for node in nodes:
        nodes_data.append({
            "id": node.id,
            "type": node.node_type,
            "title": node.title,
            "description": node.description,
            "impact_level": node.impact_level,
            "time_horizon": node.time_horizon,
            "confidence": node.confidence,
            "label": NodeType.get_label(node.node_type),
            "icon": NodeType.get_icon(node.node_type),
        })
    
    # 构建关系数据
    links_data = []
    for link in links:
        links_data.append({
            "source": link.source_node_id,
            "target": link.target_node_id,
            "type": link.link_type,
            "strength": link.strength,
            "description": link.description,
        })
    
    # 生成Mermaid语法
    mermaid_code = _generate_mermaid(nodes, links)
    
    return {
        "nodes": nodes_data,
        "links": links_data,
        "mermaid": mermaid_code,
    }


def _generate_mermaid(nodes: list, links: list) -> str:
    """
    生成Mermaid流程图语法
    
    Args:
        nodes: 因果节点列表
        links: 因果关系列表
    
    Returns:
        Mermaid语法字符串
    """
    if not nodes:
        return ""
    
    lines = ["graph LR"]
    
    # 节点ID映射（避免Mermaid语法问题）
    id_map = {}
    for i, node in enumerate(nodes):
        safe_id = f"N{i}"
        id_map[node.id] = safe_id
        
        # 转义特殊字符
        title = node.title.replace('"', "'").replace("[", "(").replace("]", ")")
        icon = NodeType.get_icon(node.node_type)
        label = NodeType.get_label(node.node_type)
        
        # 节点定义
        lines.append(f'    {safe_id}["{icon} {title}"]')
    
    # 关系定义
    link_type_labels = {
        "causes": "导致",
        "enables": "促成",
        "leads_to": "引发",
        "triggers": "触发",
    }
    
    for link in links:
        source_id = id_map.get(link.source_node_id)
        target_id = id_map.get(link.target_node_id)
        
        if source_id and target_id:
            label = link_type_labels.get(link.link_type, "影响")
            if link.description:
                label = link.description[:20].replace('"', "'")
            lines.append(f'    {source_id} -->|{label}| {target_id}')
    
    return "\n".join(lines)
