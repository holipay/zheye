from datetime import date, datetime, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_session
from models.event import Event
from models.knowledge import EventKnowledge, EventKnowledgeAtom, KnowledgeAtom
from models.causal_chain import CausalNode, CausalLink
from models.event_representation import EventRepresentation, HistoricalAnalogy
from models.scenario import EventScenario
from app.cache import get_cached, set_cached
from fastapi import Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from app.routes.api_common import router, templates, _get_api_context, _get_event_and_articles


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


# ============================================================
# 知识模型 API
# ============================================================

@router.get("/events/{event_id}/knowledge", response_class=HTMLResponse)
async def get_event_knowledge(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """获取事件的知识框架（背景、缺口、因果链）"""
    cache_key = f"api:events:knowledge:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    result = await session.execute(
        select(EventKnowledge).where(EventKnowledge.event_id == event_id)
    )
    knowledge = result.scalar_one_or_none()
    
    if not knowledge:
        return templates.TemplateResponse(request=request, name="partials/knowledge_empty.html", context={
            "event_id": event_id,
            "lang": lang,
        })
    
    # 获取关联的知识原子
    atoms_query = (
        select(KnowledgeAtom, EventKnowledgeAtom.relevance, EventKnowledgeAtom.position, EventKnowledgeAtom.is_required)
        .join(EventKnowledgeAtom, EventKnowledgeAtom.atom_id == KnowledgeAtom.id)
        .where(EventKnowledgeAtom.event_id == event_id)
        .where(KnowledgeAtom.lang == lang)
        .order_by(EventKnowledgeAtom.position)
    )
    atoms_result = await session.execute(atoms_query)
    atoms = []
    for atom, relevance, position, is_required in atoms_result.all():
        atoms.append({
            "id": atom.id,
            "type": atom.atom_type,
            "title": atom.title,
            "content": atom.content,
            "entities": atom.entities or [],
            "keywords": atom.keywords or [],
            "relevance": relevance,
            "is_required": is_required,
        })

    response = templates.TemplateResponse(request=request, name="partials/event_knowledge.html", context={
        "event_id": event_id,
        "lang": lang,
        "background_summary": knowledge.background_summary,
        "knowledge_gaps": knowledge.knowledge_gaps or [],
        "causal_chain": knowledge.causal_chain or [],
        "key_concepts": knowledge.key_concepts or [],
        "atoms": atoms,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/knowledge/analyze")
async def trigger_knowledge_analysis(
    event_id: str,
    session: AsyncSession = Depends(get_session),
):
    """触发事件知识分析（手动或自动）"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.knowledge import analyze_event_knowledge
    
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    # 调用AI分析
    ai_client = DeepSeekClient()
    analysis = await analyze_event_knowledge(event_data, articles, ai_client)
    
    if not analysis:
        raise HTTPException(status_code=500, detail="知识分析失败")
    
    # 保存知识框架
    existing = await session.execute(
        select(EventKnowledge).where(EventKnowledge.event_id == event_id)
    )
    ek = existing.scalar_one_or_none()
    
    if ek:
        # 更新
        ek.background_summary = analysis.get('background_summary')
        ek.knowledge_gaps = analysis.get('knowledge_gaps')
        ek.causal_chain = analysis.get('causal_chain')
        ek.key_concepts = analysis.get('key_concepts')
        ek.ai_model = analysis.get('ai_model')
        ek.ai_confidence = analysis.get('ai_confidence')
        ek.analysis_version += 1
    else:
        # 新建
        ek = EventKnowledge(
            event_id=event_id,
            background_summary=analysis.get('background_summary'),
            knowledge_gaps=analysis.get('knowledge_gaps'),
            causal_chain=analysis.get('causal_chain'),
            key_concepts=analysis.get('key_concepts'),
            ai_model=analysis.get('ai_model'),
            ai_confidence=analysis.get('ai_confidence'),
        )
        session.add(ek)
    
    # 保存知识原子
    for atom_data in analysis.get('knowledge_atoms', []):
        # 查找或创建知识原子
        existing_atom = await session.execute(
            select(KnowledgeAtom).where(
                KnowledgeAtom.title == atom_data['title'],
                KnowledgeAtom.lang == 'zh'
            )
        )
        atom = existing_atom.scalar_one_or_none()
        
        if not atom:
            atom = KnowledgeAtom(
                atom_type=atom_data['atom_type'],
                title=atom_data['title'],
                content=atom_data['content'],
                category=event.category,
                entities=atom_data.get('entities'),
                keywords=atom_data.get('keywords'),
                lang='zh',
            )
            session.add(atom)
            await session.flush()  # 获取ID
        
        # 关联
        existing_link = await session.execute(
            select(EventKnowledgeAtom).where(
                EventKnowledgeAtom.event_id == event_id,
                EventKnowledgeAtom.atom_id == atom.id
            )
        )
        if not existing_link.scalar():
            link = EventKnowledgeAtom(
                event_id=event_id,
                atom_id=atom.id,
                relevance=1.0,
                position=len(analysis.get('knowledge_atoms', [])),
            )
            session.add(link)
    
    await session.commit()
    
    # 清除缓存
    from app.cache import invalidate_cache
    invalidate_cache(f"api:events:knowledge:{event_id}")
    
    return {"status": "ok", "event_id": event_id, "version": ek.analysis_version}


# ============================================================
# 因果链 API
# ============================================================

@router.get("/events/{event_id}/causal-chain", response_class=HTMLResponse)
async def get_event_causal_chain(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """获取事件的因果链结构"""
    cache_key = f"api:events:causal:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    # 获取因果节点
    nodes_result = await session.execute(
        select(CausalNode)
        .where(CausalNode.event_id == event_id)
        .order_by(CausalNode.node_type, CausalNode.id)
    )
    nodes = nodes_result.scalars().all()
    
    if not nodes:
        return templates.TemplateResponse(request=request, name="partials/causal_chain_empty.html", context={
            "event_id": event_id,
            "lang": lang,
        })
    
    # 获取因果关系
    node_ids = [n.id for n in nodes]
    links_result = await session.execute(
        select(CausalLink)
        .where(CausalLink.source_node_id.in_(node_ids))
    )
    links = links_result.scalars().all()
    
    # 构建节点数据
    nodes_data = []
    for node in nodes:
        nodes_data.append({
            "id": node.id,
            "type": node.node_type,
            "title": node.title,
            "description": node.description,
            "probability": node.probability,
            "impact_level": node.impact_level,
            "time_horizon": node.time_horizon,
            "entities": node.entities or [],
            "confidence": node.confidence,
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

    response = templates.TemplateResponse(request=request, name="partials/causal_chain.html", context={
        "event_id": event_id,
        "lang": lang,
        "nodes": nodes_data,
        "links": links_data,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/causal-chain/analyze")
async def trigger_causal_chain_analysis(
    event_id: str,
    session: AsyncSession = Depends(get_session),
):
    """触发因果链分析"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.knowledge import analyze_causal_chain
    
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    # 调用AI分析
    ai_client = DeepSeekClient()
    analysis = await analyze_causal_chain(event_data, articles, ai_client)
    
    if not analysis:
        raise HTTPException(status_code=500, detail="因果链分析失败")
    
    # 删除旧的因果节点
    old_nodes = await session.execute(
        select(CausalNode).where(CausalNode.event_id == event_id)
    )
    for node in old_nodes.scalars().all():
        await session.delete(node)
    
    # 保存新的因果节点
    node_id_map = {}  # AI返回的ID -> 数据库ID
    for node_data in analysis.get('nodes', []):
        node = CausalNode(
            event_id=event_id,
            node_type=node_data['node_type'],
            title=node_data['title'],
            description=node_data.get('description'),
            probability=node_data.get('probability'),
            impact_level=node_data.get('impact_level'),
            time_horizon=node_data.get('time_horizon'),
            entities=node_data.get('entities'),
            confidence=node_data.get('confidence', 0.8),
        )
        session.add(node)
        await session.flush()
        node_id_map[node_data['id']] = node.id
    
    # 保存因果关系
    for link_data in analysis.get('links', []):
        source_id = node_id_map.get(link_data['source'])
        target_id = node_id_map.get(link_data['target'])
        
        if source_id and target_id:
            link = CausalLink(
                source_node_id=source_id,
                target_node_id=target_id,
                link_type=link_data.get('link_type', 'causes'),
                strength=link_data.get('strength', 1.0),
                description=link_data.get('description'),
            )
            session.add(link)
    
    await session.commit()
    
    # 清除缓存
    from app.cache import invalidate_cache
    invalidate_cache(f"api:events:causal:{event_id}")
    
    return {
        "status": "ok",
        "event_id": event_id,
        "nodes_count": len(analysis.get('nodes', [])),
        "links_count": len(analysis.get('links', [])),
        "summary": analysis.get('summary'),
    }


# ============================================================
# 历史类比检索 API
# ============================================================

@router.get("/events/{event_id}/analogies", response_class=HTMLResponse)
async def get_event_analogies(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """获取事件的历史类比"""
    cache_key = f"api:events:analogies:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    # 获取事件表征
    repr_result = await session.execute(
        select(EventRepresentation).where(EventRepresentation.event_id == event_id)
    )
    source_repr = repr_result.scalar_one_or_none()
    
    # 获取历史类比
    analogies_result = await session.execute(
        select(HistoricalAnalogy, Event)
        .join(Event, Event.event_id == HistoricalAnalogy.target_event_id)
        .where(HistoricalAnalogy.source_event_id == event_id)
        .order_by(HistoricalAnalogy.overall_similarity.desc())
        .limit(5)
    )
    analogies = []
    for analogy, target_event in analogies_result.all():
        analogies.append({
            "id": analogy.id,
            "target_event_id": analogy.target_event_id,
            "target_title": target_event.title,
            "target_category": target_event.category,
            "overall_similarity": analogy.overall_similarity,
            "causal_similarity": analogy.causal_similarity,
            "decision_similarity": analogy.decision_similarity,
            "constraint_similarity": analogy.constraint_similarity,
            "mechanism_similarity": analogy.mechanism_similarity,
            "game_similarity": analogy.game_similarity,
            "analogy_type": analogy.analogy_type,
            "analogy_summary": analogy.analogy_summary,
            "key_insight": analogy.key_insight,
            "lessons_learned": analogy.lessons_learned,
            "surface_differences": analogy.surface_differences or [],
            "structural_differences": analogy.structural_differences or [],
        })

    if not analogies and not source_repr:
        return templates.TemplateResponse(request=request, name="partials/analogy_empty.html", context={
            "event_id": event_id,
            "lang": lang,
        })

    response = templates.TemplateResponse(request=request, name="partials/event_analogies.html", context={
        "event_id": event_id,
        "lang": lang,
        "source_repr": {
            "causal_pattern": source_repr.causal_pattern_desc if source_repr else None,
            "economic_principle": source_repr.economic_principle_desc if source_repr else None,
        } if source_repr else None,
        "analogies": analogies,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/analogies/analyze")
async def trigger_analogy_analysis(
    event_id: str,
    session: AsyncSession = Depends(get_session),
):
    """触发历史类比分析"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.analogy import extract_event_representation, analyze_analogy, compute_structural_similarity
    
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    ai_client = DeepSeekClient()
    
    # 步骤1: 提取当前事件的表征
    repr_result = await extract_event_representation(event_data, articles, ai_client)
    if not repr_result:
        raise HTTPException(status_code=500, detail="表征提取失败")
    
    # 保存表征
    existing_repr = await session.execute(
        select(EventRepresentation).where(EventRepresentation.event_id == event_id)
    )
    er = existing_repr.scalar_one_or_none()
    
    surface = repr_result.get('surface', {})
    structural = repr_result.get('structural', {})
    abstract = repr_result.get('abstract', {})
    
    if er:
        er.surface_summary = surface.get('summary')
        er.surface_entities = surface.get('entities')
        er.surface_numbers = surface.get('numbers')
        er.causal_pattern = structural.get('causal_pattern')
        er.causal_pattern_desc = structural.get('causal_pattern_desc')
        er.decision_logic = structural.get('decision_logic')
        er.transmission_mechanism = structural.get('transmission_mechanism')
        er.constraint_conditions = structural.get('constraint_conditions')
        er.economic_principle = abstract.get('economic_principle')
        er.economic_principle_desc = abstract.get('economic_principle_desc')
        er.game_theory_structure = abstract.get('game_theory_structure')
        er.institutional_context = abstract.get('institutional_context')
        er.ai_model = repr_result.get('ai_model')
        er.ai_confidence = repr_result.get('ai_confidence')
    else:
        er = EventRepresentation(
            event_id=event_id,
            surface_summary=surface.get('summary'),
            surface_entities=surface.get('entities'),
            surface_numbers=surface.get('numbers'),
            causal_pattern=structural.get('causal_pattern'),
            causal_pattern_desc=structural.get('causal_pattern_desc'),
            decision_logic=structural.get('decision_logic'),
            transmission_mechanism=structural.get('transmission_mechanism'),
            constraint_conditions=structural.get('constraint_conditions'),
            economic_principle=abstract.get('economic_principle'),
            economic_principle_desc=abstract.get('economic_principle_desc'),
            game_theory_structure=abstract.get('game_theory_structure'),
            institutional_context=abstract.get('institutional_context'),
            ai_model=repr_result.get('ai_model'),
            ai_confidence=repr_result.get('ai_confidence'),
        )
        session.add(er)
    
    await session.flush()
    
    # 步骤2: 查找候选历史事件（基于规则的预筛选）
    # 优先匹配相同因果模式或经济学原理的事件
    candidates_query = (
        select(EventRepresentation)
        .where(EventRepresentation.event_id != event_id)
        .where(
            (EventRepresentation.causal_pattern == structural.get('causal_pattern')) |
            (EventRepresentation.economic_principle == abstract.get('economic_principle'))
        )
        .limit(10)
    )
    candidates_result = await session.execute(candidates_query)
    candidates = candidates_result.scalars().all()
    
    # 步骤3: 对每个候选进行详细的类比分析
    analogies_created = 0
    for candidate in candidates:
        # 检查是否已存在
        existing = await session.execute(
            select(HistoricalAnalogy).where(
                HistoricalAnalogy.source_event_id == event_id,
                HistoricalAnalogy.target_event_id == candidate.event_id
            )
        )
        if existing.scalar():
            continue
        
        # 计算规则相似度
        rule_scores = compute_structural_similarity(
            repr_result,
            {
                'structural': {
                    'causal_pattern': candidate.causal_pattern,
                    'constraint_conditions': candidate.constraint_conditions or [],
                },
                'abstract': {
                    'economic_principle': candidate.economic_principle,
                }
            }
        )
        
        # 如果规则相似度太低，跳过AI分析
        if rule_scores['overall'] < 0.3:
            continue
        
        # 调用AI进行详细类比分析
        source_data = {
            'title': event.title,
            'causal_pattern_desc': structural.get('causal_pattern_desc'),
            'decision_logic': structural.get('decision_logic'),
            'transmission_mechanism': structural.get('transmission_mechanism'),
            'economic_principle_desc': abstract.get('economic_principle_desc'),
        }
        target_data = {
            'title': candidate.surface_summary,
            'causal_pattern_desc': candidate.causal_pattern_desc,
            'decision_logic': candidate.decision_logic,
            'transmission_mechanism': candidate.transmission_mechanism,
            'economic_principle_desc': candidate.economic_principle_desc,
        }
        
        analogy_result = await analyze_analogy(source_data, target_data, ai_client)
        if not analogy_result:
            continue
        
        # 保存类比
        analogy = HistoricalAnalogy(
            source_event_id=event_id,
            target_event_id=candidate.event_id,
            causal_similarity=analogy_result.get('causal_similarity'),
            decision_similarity=analogy_result.get('decision_similarity'),
            constraint_similarity=analogy_result.get('constraint_similarity'),
            mechanism_similarity=analogy_result.get('mechanism_similarity'),
            game_similarity=analogy_result.get('game_similarity'),
            overall_similarity=analogy_result.get('overall_similarity'),
            analogy_type=analogy_result.get('analogy_type'),
            analogy_summary=analogy_result.get('analogy_summary'),
            key_insight=analogy_result.get('key_insight'),
            lessons_learned=analogy_result.get('lessons_learned'),
            surface_differences=analogy_result.get('surface_differences'),
            structural_differences=analogy_result.get('structural_differences'),
            confidence=analogy_result.get('confidence'),
            ai_model=analogy_result.get('ai_model'),
        )
        session.add(analogy)
        analogies_created += 1
    
    await session.commit()
    
    # 清除缓存
    from app.cache import invalidate_cache
    invalidate_cache(f"api:events:analogies:{event_id}")
    
    return {
        "status": "ok",
        "event_id": event_id,
        "representation_extracted": True,
        "candidates_found": len(candidates),
        "analogies_created": analogies_created,
    }


# ============================================================
# 未来情景推演 API
# ============================================================

@router.get("/events/{event_id}/scenarios", response_class=HTMLResponse)
async def get_event_scenarios(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """获取事件的情景推演框架"""
    cache_key = f"api:events:scenarios:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    result = await session.execute(
        select(EventScenario).where(EventScenario.event_id == event_id)
    )
    scenario = result.scalar_one_or_none()
    
    if not scenario:
        return templates.TemplateResponse(request=request, name="partials/scenario_empty.html", context={
            "event_id": event_id,
            "lang": lang,
        })

    response = templates.TemplateResponse(request=request, name="partials/event_scenarios.html", context={
        "event_id": event_id,
        "lang": lang,
        "key_variables": scenario.key_variables or [],
        "observation_signals": scenario.observation_signals or [],
        "scenarios": scenario.scenarios or [],
        "thinking_questions": scenario.thinking_questions or [],
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/scenarios/analyze")
async def trigger_scenario_analysis(
    event_id: str,
    session: AsyncSession = Depends(get_session),
):
    """触发情景推演分析"""
    from scraper.pipeline.ai_analysis import DeepSeekClient
    from scraper.pipeline.scenario import analyze_scenarios
    
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    # 获取因果模式（如果已有表征）
    repr_result = await session.execute(
        select(EventRepresentation).where(EventRepresentation.event_id == event_id)
    )
    representation = repr_result.scalar_one_or_none()
    causal_pattern = representation.causal_pattern_desc if representation else None
    
    # 调用AI分析
    ai_client = DeepSeekClient()
    analysis = await analyze_scenarios(event_data, articles, ai_client, causal_pattern)
    
    if not analysis:
        raise HTTPException(status_code=500, detail="情景分析失败")
    
    # 保存情景推演
    existing = await session.execute(
        select(EventScenario).where(EventScenario.event_id == event_id)
    )
    es = existing.scalar_one_or_none()
    
    if es:
        es.key_variables = analysis.get('key_variables')
        es.observation_signals = analysis.get('observation_signals')
        es.scenarios = analysis.get('scenarios')
        es.thinking_questions = analysis.get('thinking_questions')
        es.ai_model = analysis.get('ai_model')
        es.ai_confidence = analysis.get('ai_confidence')
    else:
        es = EventScenario(
            event_id=event_id,
            key_variables=analysis.get('key_variables'),
            observation_signals=analysis.get('observation_signals'),
            scenarios=analysis.get('scenarios'),
            thinking_questions=analysis.get('thinking_questions'),
            ai_model=analysis.get('ai_model'),
            ai_confidence=analysis.get('ai_confidence'),
        )
        session.add(es)
    
    await session.commit()
    
    # 清除缓存
    from app.cache import invalidate_cache
    invalidate_cache(f"api:events:scenarios:{event_id}")
    
    return {
        "status": "ok",
        "event_id": event_id,
        "key_variables_count": len(analysis.get('key_variables', [])),
        "scenarios_count": len(analysis.get('scenarios', [])),
    }
