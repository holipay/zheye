"""
深度分析路由
提供知识框架、因果链、历史类比、情景推演的 API 端点
"""

import logging
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_session
from models.event import Event
from app.cache import get_cached, set_cached, invalidate_cache
from app.auth import verify_admin_credentials
from app.csrf import csrf_protect
from app.routes.api_common import _get_event_and_articles
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from deep_analyst.ai_analysis import DeepSeekClient
from deep_analyst.knowledge import analyze_event_knowledge, analyze_causal_chain, find_relevant_atoms
from deep_analyst.analogy import extract_event_representation, analyze_analogy, compute_structural_similarity
from deep_analyst.scenario import analyze_scenarios
from deep_analyst.models.knowledge import EventKnowledge, EventKnowledgeAtom, KnowledgeAtom
from deep_analyst.models.causal_chain import CausalNode, CausalLink, NodeType
from deep_analyst.models.event_representation import EventRepresentation, HistoricalAnalogy
from deep_analyst.models.scenario import EventScenario
from app.errors import ErrorMessages as Err

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deep-analyst", tags=["deep-analyst"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _generate_causal_mermaid(nodes: list, links: list) -> str:
    """
    生成因果链的Mermaid流程图语法
    
    Args:
        nodes: 因果节点列表
        links: 因果关系列表
    
    Returns:
        Mermaid语法字符串
    """
    from common.mermaid import generate_causal_mermaid
    return generate_causal_mermaid(nodes, links)


# ============================================================
# 知识框架 API
# ============================================================

@router.get("/events/{event_id}/knowledge", response_class=HTMLResponse)
async def get_event_knowledge(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """获取事件的知识框架"""
    cache_key = f"deep:knowledge:{event_id}:{lang}"
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
    
    atoms_query = (
        select(KnowledgeAtom, EventKnowledgeAtom.relevance, EventKnowledgeAtom.position)
        .join(EventKnowledgeAtom, EventKnowledgeAtom.atom_id == KnowledgeAtom.id)
        .where(EventKnowledgeAtom.event_id == event_id)
        .where(KnowledgeAtom.lang == lang)
        .order_by(EventKnowledgeAtom.position)
    )
    atoms_result = await session.execute(atoms_query)
    atoms = [
        {
            "id": atom.id,
            "type": atom.atom_type,
            "title": atom.title,
            "content": atom.content,
            "relevance": relevance,
        }
        for atom, relevance, position in atoms_result.all()
    ]

    response = templates.TemplateResponse(request=request, name="partials/deep_knowledge.html", context={
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
    _: bool = Depends(verify_admin_credentials),
    __: bool = Depends(csrf_protect),
    session: AsyncSession = Depends(get_session),
):
    """触发知识分析"""
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    ai_client = DeepSeekClient()

    # 查找已有相关知识原子
    existing_atoms = await find_relevant_atoms(
        session=session,
        category=event_data.get("category"),
    )

    analysis = await analyze_event_knowledge(event_data, articles, ai_client, existing_atoms)
    
    if not analysis:
        raise HTTPException(status_code=500, detail=Err.KNOWLEDGE_ANALYSIS_FAILED)
    
    existing = await session.execute(
        select(EventKnowledge).where(EventKnowledge.event_id == event_id)
    )
    ek = existing.scalar_one_or_none()
    
    if ek:
        ek.background_summary = analysis.get('background_summary')
        ek.knowledge_gaps = analysis.get('knowledge_gaps')
        ek.causal_chain = analysis.get('causal_chain')
        ek.key_concepts = analysis.get('key_concepts')
        ek.ai_model = analysis.get('ai_model')
        ek.ai_confidence = analysis.get('ai_confidence')
        ek.analysis_version += 1
    else:
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
    
    atoms_data = analysis.get('knowledge_atoms', [])
    if atoms_data:
        # 批量查询已有的知识原子
        atom_titles = [(a['title'], 'zh') for a in atoms_data]
        result = await session.execute(
            select(KnowledgeAtom).where(
                tuple_(KnowledgeAtom.title, KnowledgeAtom.lang).in_(atom_titles)
            )
        )
        existing_atoms = {(a.title, a.lang): a for a in result.scalars()}

        # 创建新原子 + 收集所有 atom_id
        atom_ids = []
        for atom_data in atoms_data:
            key = (atom_data['title'], 'zh')
            atom = existing_atoms.get(key)

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
                await session.flush()
                existing_atoms[key] = atom

            atom_ids.append(atom.id)

        # 添加复用的原子 ID
        reused_ids = [aid for aid in analysis.get('_reused_atom_ids', []) if isinstance(aid, int)]
        atom_ids.extend(reused_ids)

        # 批量查询已有的关联
        if atom_ids:
            result = await session.execute(
                select(EventKnowledgeAtom.atom_id).where(
                    EventKnowledgeAtom.event_id == event_id,
                    EventKnowledgeAtom.atom_id.in_(atom_ids),
                )
            )
            existing_link_ids = {row[0] for row in result.fetchall()}

            # 批量创建新关联
            for atom_data in atoms_data:
                atom = existing_atoms.get((atom_data['title'], 'zh'))
                if atom and atom.id not in existing_link_ids:
                    session.add(EventKnowledgeAtom(
                        event_id=event_id,
                        atom_id=atom.id,
                        relevance=1.0,
                        position=len(atoms_data),
                    ))

            for atom_id in reused_ids:
                if atom_id not in existing_link_ids:
                    session.add(EventKnowledgeAtom(
                        event_id=event_id,
                        atom_id=atom_id,
                        relevance=0.8,
                        position=999,
                    ))
    
    await session.commit()
    invalidate_cache(f"deep:knowledge:{event_id}")
    
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
    """获取事件的因果链"""
    cache_key = f"deep:causal:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

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

    links_result = await session.execute(
        select(CausalLink)
        .join(CausalNode, CausalLink.source_node_id == CausalNode.id)
        .where(CausalNode.event_id == event_id)
    )
    links = links_result.scalars().all()

    node_map = {n.id: n for n in nodes}
    nodes_data = []
    for node in nodes:
        nodes_data.append({
            "id": node.id,
            "node_type": node.node_type,
            "title": node.title,
            "description": node.description,
            "probability": node.probability,
            "impact_level": node.impact_level,
            "time_horizon": node.time_horizon,
            "entities": node.entities or [],
            "confidence": node.confidence,
        })

    links_data = []
    for link in links:
        source = node_map.get(link.source_node_id)
        target = node_map.get(link.target_node_id)
        if source and target:
            links_data.append({
                "source_id": link.source_node_id,
                "target_id": link.target_node_id,
                "source_title": source.title,
                "target_title": target.title,
                "link_type": link.link_type,
                "strength": link.strength,
                "description": link.description,
            })

    # 生成Mermaid语法
    mermaid_code = _generate_causal_mermaid(nodes, links)

    response = templates.TemplateResponse(request=request, name="partials/causal_chain.html", context={
        "event_id": event_id,
        "lang": lang,
        "nodes": nodes_data,
        "links": links_data,
        "mermaid": mermaid_code,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/causal-chain/analyze")
async def trigger_causal_chain_analysis(
    event_id: str,
    _: bool = Depends(verify_admin_credentials),
    __: bool = Depends(csrf_protect),
    session: AsyncSession = Depends(get_session),
):
    """触发因果链分析"""
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    ai_client = DeepSeekClient()
    analysis = await analyze_causal_chain(event_data, articles, ai_client)
    
    if not analysis:
        raise HTTPException(status_code=500, detail=Err.CAUSAL_CHAIN_ANALYSIS_FAILED)
    
    old_nodes = await session.execute(
        select(CausalNode).where(CausalNode.event_id == event_id)
    )
    for node in old_nodes.scalars().all():
        await session.delete(node)
    
    node_id_map = {}
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
    invalidate_cache(f"deep:causal:{event_id}")
    
    return {
        "status": "ok",
        "event_id": event_id,
        "nodes_count": len(analysis.get('nodes', [])),
        "links_count": len(analysis.get('links', [])),
    }


# ============================================================
# 历史类比 API
# ============================================================

@router.get("/events/{event_id}/analogies", response_class=HTMLResponse)
async def get_event_analogies(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """获取事件的历史类比"""
    cache_key = f"deep:analogies:{event_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    representation_result = await session.execute(
        select(EventRepresentation).where(EventRepresentation.event_id == event_id)
    )
    representation = representation_result.scalar_one_or_none()

    if not representation:
        return templates.TemplateResponse(request=request, name="partials/analogy_empty.html", context={
            "event_id": event_id,
            "lang": lang,
        })

    analogies_result = await session.execute(
        select(HistoricalAnalogy)
        .where(HistoricalAnalogy.source_event_id == event_id)
        .order_by(HistoricalAnalogy.overall_similarity.desc())
        .limit(10)
    )
    analogies = analogies_result.scalars().all()

    if not analogies:
        return templates.TemplateResponse(request=request, name="partials/analogy_empty.html", context={
            "event_id": event_id,
            "lang": lang,
        })

    analogies_data = []
    for analogy in analogies:
        analogies_data.append({
            "id": analogy.id,
            "target_event_id": analogy.target_event_id,
            "causal_similarity": analogy.causal_similarity,
            "decision_similarity": analogy.decision_similarity,
            "constraint_similarity": analogy.constraint_similarity,
            "mechanism_similarity": analogy.mechanism_similarity,
            "game_similarity": analogy.game_similarity,
            "overall_similarity": analogy.overall_similarity,
            "analogy_type": analogy.analogy_type,
            "analogy_summary": analogy.analogy_summary,
            "key_insight": analogy.key_insight,
            "lessons_learned": analogy.lessons_learned,
            "surface_differences": analogy.surface_differences or [],
            "structural_differences": analogy.structural_differences or [],
            "confidence": analogy.confidence,
        })

    representation_data = {
        "surface_summary": representation.surface_summary,
        "surface_entities": representation.surface_entities or [],
        "causal_pattern": representation.causal_pattern,
        "causal_pattern_desc": representation.causal_pattern_desc,
        "decision_logic": representation.decision_logic,
        "transmission_mechanism": representation.transmission_mechanism,
        "economic_principle": representation.economic_principle,
        "economic_principle_desc": representation.economic_principle_desc,
    }

    response = templates.TemplateResponse(request=request, name="partials/event_analogies.html", context={
        "event_id": event_id,
        "lang": lang,
        "representation": representation_data,
        "analogies": analogies_data,
    })
    set_cached(cache_key, response.body.decode(), ttl=600)
    return response


@router.post("/events/{event_id}/analogies/analyze")
async def trigger_analogy_analysis(
    event_id: str,
    _: bool = Depends(verify_admin_credentials),
    __: bool = Depends(csrf_protect),
    session: AsyncSession = Depends(get_session),
):
    """触发历史类比分析"""
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    ai_client = DeepSeekClient()
    
    repr_result = await extract_event_representation(event_data, articles, ai_client)
    if not repr_result:
        raise HTTPException(status_code=500, detail=Err.REPRESENTATION_EXTRACTION_FAILED)
    
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
    
    candidate_ids = [c.event_id for c in candidates]
    existing_result = await session.execute(
        select(HistoricalAnalogy.target_event_id)
        .where(
            HistoricalAnalogy.source_event_id == event_id,
            HistoricalAnalogy.target_event_id.in_(candidate_ids)
        )
    )
    existing_targets = {row[0] for row in existing_result.fetchall()}
    
    analogies_created = 0
    for candidate in candidates:
        if candidate.event_id in existing_targets:
            continue
        
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
        
        if rule_scores['overall'] < 0.3:
            continue
        
        # 使用 savepoint 隔离每个候选事件的分析，单个失败不影响其他
        try:
            async with session.begin_nested():
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
        except Exception as e:
            logger.warning(f"类比分析失败 (candidate={candidate.event_id}): {e}")
    
    await session.commit()
    invalidate_cache(f"deep:analogies:{event_id}")
    
    return {
        "status": "ok",
        "event_id": event_id,
        "candidates_found": len(candidates),
        "analogies_created": analogies_created,
    }


# ============================================================
# 情景推演 API
# ============================================================

@router.get("/events/{event_id}/scenarios", response_class=HTMLResponse)
async def get_event_scenarios(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """获取事件的情景推演"""
    cache_key = f"deep:scenarios:{event_id}:{lang}"
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
    _: bool = Depends(verify_admin_credentials),
    __: bool = Depends(csrf_protect),
    session: AsyncSession = Depends(get_session),
):
    """触发情景推演分析"""
    event, event_data, articles = await _get_event_and_articles(session, event_id)
    
    repr_result = await session.execute(
        select(EventRepresentation).where(EventRepresentation.event_id == event_id)
    )
    representation = repr_result.scalar_one_or_none()
    causal_pattern = representation.causal_pattern_desc if representation else None
    
    ai_client = DeepSeekClient()
    analysis = await analyze_scenarios(event_data, articles, ai_client, causal_pattern)
    
    if not analysis:
        raise HTTPException(status_code=500, detail=Err.SCENARIO_ANALYSIS_FAILED)
    
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
    invalidate_cache(f"deep:scenarios:{event_id}")
    
    return {
        "status": "ok",
        "event_id": event_id,
        "key_variables_count": len(analysis.get('key_variables', [])),
        "scenarios_count": len(analysis.get('scenarios', [])),
    }


# ============================================================
# 知识原子复用统计 API
# ============================================================

@router.get("/knowledge/stats")
async def get_knowledge_stats(
    session: AsyncSession = Depends(get_session),
):
    """获取知识原子复用统计"""
    from deep_analyst.knowledge import get_reuse_statistics
    
    stats = await get_reuse_statistics(session)
    return stats


@router.get("/knowledge/atoms")
async def get_knowledge_atoms(
    session: AsyncSession = Depends(get_session),
    category: str = None,
    min_quality: float = 0.0,
    limit: int = 50,
):
    """获取知识原子列表"""
    query = select(KnowledgeAtom).where(KnowledgeAtom.quality_score >= min_quality)
    
    if category:
        query = query.where(KnowledgeAtom.category == category)
    
    query = query.order_by(KnowledgeAtom.quality_score.desc()).limit(limit)
    
    result = await session.execute(query)
    atoms = result.scalars().all()
    
    return {
        "atoms": [
            {
                "id": atom.id,
                "atom_type": atom.atom_type,
                "title": atom.title,
                "content": atom.content[:200],
                "category": atom.category,
                "entities": atom.entities,
                "keywords": atom.keywords,
                "confidence": atom.confidence,
                "quality_score": atom.quality_score,
                "reuse_count": atom.reuse_count,
                "version": atom.version,
                "last_reused_at": atom.last_reused_at.isoformat() if atom.last_reused_at else None,
                "created_at": atom.created_at.isoformat() if atom.created_at else None,
            }
            for atom in atoms
        ],
        "total": len(atoms),
    }


@router.post("/knowledge/atoms/{atom_id}/update")
async def update_atom(
    atom_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_admin_credentials),
    __: bool = Depends(csrf_protect),
):
    """更新知识原子（创建新版本）"""
    from deep_analyst.knowledge import update_knowledge_atom
    
    body = await request.json()
    new_content = body.get("content")
    new_title = body.get("title")
    reason = body.get("reason")
    
    new_atom = await update_knowledge_atom(session, atom_id, new_content, new_title, reason)
    
    if not new_atom:
        raise HTTPException(status_code=404, detail=Err.KNOWLEDGE_ATOM_NOT_FOUND)
    
    await session.commit()
    
    return {
        "status": "ok",
        "old_id": atom_id,
        "new_id": new_atom.id,
        "version": new_atom.version,
    }


@router.post("/knowledge/quality/decay")
async def trigger_quality_decay(
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_admin_credentials),
    __: bool = Depends(csrf_protect),
):
    """触发质量衰减计算"""
    from deep_analyst.knowledge import apply_quality_decay
    
    updated = await apply_quality_decay(session)
    await session.commit()
    
    return {
        "status": "ok",
        "updated_count": updated,
    }
