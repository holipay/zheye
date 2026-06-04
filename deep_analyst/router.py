"""
深度分析路由
提供知识框架、因果链、历史类比、情景推演的 API 端点
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import get_session
from models.event import Event
from app.cache import get_cached, set_cached, invalidate_cache
from app.auth import verify_admin_credentials
from app.csrf import csrf_protect
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from deep_analyst.ai_analysis import DeepSeekClient
from deep_analyst.knowledge import analyze_event_knowledge, analyze_causal_chain
from deep_analyst.analogy import extract_event_representation, analyze_analogy, compute_structural_similarity
from deep_analyst.scenario import analyze_scenarios
from deep_analyst.models.knowledge import EventKnowledge, EventKnowledgeAtom, KnowledgeAtom
from deep_analyst.models.causal_chain import CausalNode, CausalLink
from deep_analyst.models.event_representation import EventRepresentation, HistoricalAnalogy
from deep_analyst.models.scenario import EventScenario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deep-analyst", tags=["deep-analyst"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


async def _get_event_and_articles(session: AsyncSession, event_id: str, max_articles: int = 5):
    """获取事件及其关联文章"""
    result = await session.execute(select(Event).where(Event.event_id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="事件未找到")
    
    articles = []
    if event.related_articles:
        for article_ref in event.related_articles[:max_articles]:
            if isinstance(article_ref, dict):
                articles.append(article_ref)
    
    event_data = {
        "title": event.title,
        "description": event.description,
        "category": event.category,
    }
    
    return event, event_data, articles


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
        return HTMLResponse(content="<p class='text-muted'>暂无知识分析数据</p>")
    
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
    analysis = await analyze_event_knowledge(event_data, articles, ai_client)
    
    if not analysis:
        raise HTTPException(status_code=500, detail="知识分析失败")
    
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
    
    for atom_data in analysis.get('knowledge_atoms', []):
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
            await session.flush()
        
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
    invalidate_cache(f"deep:knowledge:{event_id}")
    
    return {"status": "ok", "event_id": event_id, "version": ek.analysis_version}


# ============================================================
# 因果链 API
# ============================================================

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
        raise HTTPException(status_code=500, detail="因果链分析失败")
    
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
        raise HTTPException(status_code=500, detail="表征提取失败")
    
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
        raise HTTPException(status_code=500, detail="情景分析失败")
    
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
