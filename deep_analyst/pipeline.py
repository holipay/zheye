"""
深度分析流水线
编排知识框架 → 因果链 → 历史类比 → 情景推演的分析流程

使用方式：
    from deep_analyst.pipeline import run_deep_analysis
    result = await run_deep_analysis(session, event_id)
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.event import Event
from deep_analyst.ai_analysis import DeepSeekClient
from deep_analyst.knowledge import analyze_event_knowledge, analyze_causal_chain
from deep_analyst.analogy import extract_event_representation, analyze_analogy, compute_structural_similarity
from deep_analyst.scenario import analyze_scenarios
from deep_analyst.models.knowledge import EventKnowledge, EventKnowledgeAtom, KnowledgeAtom
from deep_analyst.models.causal_chain import CausalNode, CausalLink
from deep_analyst.models.event_representation import EventRepresentation, HistoricalAnalogy
from deep_analyst.models.scenario import EventScenario

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """单个事件的分析结果"""
    event_id: str
    success: bool
    steps_completed: list[str] = field(default_factory=list)
    steps_failed: list[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class PipelineResult:
    """批量分析的汇总结果"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[AnalysisResult] = field(default_factory=list)
    duration_seconds: float = 0.0


async def get_events_needing_analysis(
    session: AsyncSession,
    max_events: int = 10,
    cooldown_hours: int = 24,
) -> list[dict]:
    """
    查找需要深度分析的事件

    筛选逻辑：
    1. Event 存在且 status=active
    2. EventKnowledge 不存在（从未分析过）
    3. 或 EventKnowledge.updated_at 早于 Event.last_updated（事件有新文章但分析未更新）
    4. 排除 cooldown 小时内已分析过的事件

    Args:
        session: 数据库会话
        max_events: 最多返回的事件数
        cooldown_hours: 同一事件的分析冷却时间（小时）

    Returns:
        需要分析的事件列表 [{event_id, title, description, category, related_articles}]
    """
    cooldown_cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)

    # 子查询：每个事件的最新分析时间
    last_analysis = (
        select(
            EventKnowledge.event_id,
            EventKnowledge.updated_at.label("analyzed_at"),
        )
        .subquery()
    )

    # 主查询：active 事件，且（无分析记录 或 分析过时 或 冷却期已过）
    stmt = (
        select(Event)
        .outerjoin(last_analysis, Event.event_id == last_analysis.c.event_id)
        .where(Event.status == "active")
        .where(
            # 从未分析过
            last_analysis.c.analyzed_at.is_(None)
            |
            # 分析过时：事件有更新但分析未跟上
            (
                last_analysis.c.analyzed_at.isnot(None)
                & (last_analysis.c.analyzed_at < func.date(Event.last_updated))
            )
        )
        .order_by(Event.last_updated.desc())
        .limit(max_events)
    )

    result = await session.execute(stmt)
    events = []

    for row in result.scalars():
        articles = []
        if row.related_articles:
            for ref in row.related_articles[:5]:
                if isinstance(ref, dict):
                    articles.append(ref)

        events.append({
            "event_id": row.event_id,
            "title": row.title,
            "description": row.description,
            "category": row.category,
            "related_articles": articles,
        })

    return events


async def analyze_single_event(
    session: AsyncSession,
    event_data: dict,
    ai_client: DeepSeekClient,
) -> AnalysisResult:
    """
    对单个事件执行完整的深度分析流水线

    流程：知识框架 → 因果链 → 历史类比 → 情景推演

    Args:
        session: 数据库会话
        event_data: 事件数据 {event_id, title, description, category, related_articles}
        ai_client: AI 客户端

    Returns:
        AnalysisResult
    """
    event_id = event_data["event_id"]
    start_time = datetime.utcnow()
    result = AnalysisResult(event_id=event_id, success=False)

    articles = event_data.get("related_articles", [])

    # Step 1: 知识框架
    logger.info(f"  [{event_id}] Step 1/4: 知识框架分析")
    try:
        knowledge = await analyze_event_knowledge(event_data, articles, ai_client)
        if knowledge:
            # 存储知识框架
            await _save_knowledge(session, event_id, knowledge, event_data.get("category"))
            result.steps_completed.append("knowledge")
            logger.info(f"  [{event_id}] 知识框架完成")
        else:
            result.steps_failed.append("knowledge")
            logger.warning(f"  [{event_id}] 知识框架返回空结果")
    except Exception as e:
        result.steps_failed.append("knowledge")
        logger.error(f"  [{event_id}] 知识框架失败: {e}")

    # Step 2: 因果链（依赖知识框架的背景信息）
    logger.info(f"  [{event_id}] Step 2/4: 因果链分析")
    try:
        causal = await analyze_causal_chain(event_data, articles, ai_client)
        if causal:
            await _save_causal_chain(session, event_id, causal)
            result.steps_completed.append("causal_chain")
            logger.info(f"  [{event_id}] 因果链完成 ({len(causal.get('nodes', []))} 节点)")
        else:
            result.steps_failed.append("causal_chain")
            logger.warning(f"  [{event_id}] 因果链返回空结果")
    except Exception as e:
        result.steps_failed.append("causal_chain")
        logger.error(f"  [{event_id}] 因果链失败: {e}")

    # Step 3: 历史类比
    logger.info(f"  [{event_id}] Step 3/4: 历史类比分析")
    try:
        repr_result = await extract_event_representation(event_data, articles, ai_client)
        if repr_result:
            await _save_representation(session, event_id, repr_result)
            # 尝试匹配历史类比
            analogy_count = await _find_and_save_analogies(session, event_id, event_data, repr_result, ai_client)
            result.steps_completed.append("analogy")
            logger.info(f"  [{event_id}] 历史类比完成 ({analogy_count} 条类比)")
        else:
            result.steps_failed.append("analogy")
            logger.warning(f"  [{event_id}] 表征提取返回空结果")
    except Exception as e:
        result.steps_failed.append("analogy")
        logger.error(f"  [{event_id}] 历史类比失败: {e}")

    # Step 4: 情景推演（依赖因果链的 causal_pattern_desc）
    logger.info(f"  [{event_id}] Step 4/4: 情景推演分析")
    try:
        # 获取 causal_pattern_desc 作为输入
        causal_pattern = None
        repr_row = await session.execute(
            select(EventRepresentation).where(EventRepresentation.event_id == event_id)
        )
        repr_obj = repr_row.scalar_one_or_none()
        if repr_obj:
            causal_pattern = repr_obj.causal_pattern_desc

        scenarios = await analyze_scenarios(event_data, articles, ai_client, causal_pattern)
        if scenarios:
            await _save_scenarios(session, event_id, scenarios)
            result.steps_completed.append("scenario")
            logger.info(f"  [{event_id}] 情景推演完成")
        else:
            result.steps_failed.append("scenario")
            logger.warning(f"  [{event_id}] 情景推演返回空结果")
    except Exception as e:
        result.steps_failed.append("scenario")
        logger.error(f"  [{event_id}] 情景推演失败: {e}")

    # 判断整体成功
    result.success = len(result.steps_completed) >= 1  # 至少完成一步算成功
    result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()

    return result


async def run_deep_analysis(
    session: AsyncSession,
    max_events: int = 10,
    cooldown_hours: int = 24,
    event_id: Optional[str] = None,
) -> PipelineResult:
    """
    执行批量深度分析

    Args:
        session: 数据库会话
        max_events: 最多分析的事件数
        cooldown_hours: 同一事件的分析冷却时间
        event_id: 指定事件 ID（单事件分析模式）

    Returns:
        PipelineResult
    """
    start_time = datetime.utcnow()
    pipeline_result = PipelineResult()

    # 初始化 AI 客户端
    ai_client = DeepSeekClient()
    if not ai_client.enabled:
        logger.error("DeepSeek API 未启用，请配置 DEEPSEEK_API_KEY")
        return pipeline_result

    # 获取待分析事件
    if event_id:
        # 单事件模式
        event_row = await session.execute(select(Event).where(Event.event_id == event_id))
        event = event_row.scalar_one_or_none()
        if not event:
            logger.error(f"事件不存在: {event_id}")
            return pipeline_result
        articles = []
        if event.related_articles:
            for ref in event.related_articles[:5]:
                if isinstance(ref, dict):
                    articles.append(ref)
        events = [{
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "category": event.category,
            "related_articles": articles,
        }]
    else:
        # 批量模式
        events = await get_events_needing_analysis(session, max_events, cooldown_hours)

    pipeline_result.total = len(events)

    if not events:
        logger.info("没有需要分析的事件")
        return pipeline_result

    logger.info(f"找到 {len(events)} 个待分析事件")

    # 逐个分析（串行，避免 API 过载）
    for i, event_data in enumerate(events, 1):
        event_id = event_data["event_id"]
        logger.info(f"[{i}/{len(events)}] 开始分析: {event_data['title'][:50]}...")

        try:
            result = await analyze_single_event(session, event_data, ai_client)
            pipeline_result.results.append(result)

            if result.success:
                pipeline_result.success += 1
                await session.commit()
            else:
                pipeline_result.failed += 1

        except Exception as e:
            logger.error(f"[{i}/{len(events)}] 分析异常: {e}")
            pipeline_result.failed += 1
            pipeline_result.results.append(AnalysisResult(
                event_id=event_id,
                success=False,
                error=str(e),
            ))

        # 事件间间隔，避免 API 速率限制
        if i < len(events):
            await asyncio.sleep(2)

    pipeline_result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
    return pipeline_result


# ============================================================
# 内部存储函数
# ============================================================

async def _save_knowledge(session: AsyncSession, event_id: str, analysis: dict, category: str = None):
    """存储知识框架分析结果"""
    existing = await session.execute(
        select(EventKnowledge).where(EventKnowledge.event_id == event_id)
    )
    ek = existing.scalar_one_or_none()

    if ek:
        ek.background_summary = analysis.get("background_summary")
        ek.knowledge_gaps = analysis.get("knowledge_gaps")
        ek.causal_chain = analysis.get("causal_chain")
        ek.key_concepts = analysis.get("key_concepts")
        ek.ai_model = analysis.get("ai_model")
        ek.ai_confidence = analysis.get("ai_confidence")
        ek.analysis_version += 1
    else:
        ek = EventKnowledge(
            event_id=event_id,
            background_summary=analysis.get("background_summary"),
            knowledge_gaps=analysis.get("knowledge_gaps"),
            causal_chain=analysis.get("causal_chain"),
            key_concepts=analysis.get("key_concepts"),
            ai_model=analysis.get("ai_model"),
            ai_confidence=analysis.get("ai_confidence"),
        )
        session.add(ek)

    # 存储知识原子
    for atom_data in analysis.get("knowledge_atoms", []):
        existing_atom = await session.execute(
            select(KnowledgeAtom).where(
                KnowledgeAtom.title == atom_data["title"],
                KnowledgeAtom.lang == "zh",
            )
        )
        atom = existing_atom.scalar_one_or_none()

        if not atom:
            atom = KnowledgeAtom(
                atom_type=atom_data["atom_type"],
                title=atom_data["title"],
                content=atom_data["content"],
                category=category,
                entities=atom_data.get("entities"),
                keywords=atom_data.get("keywords"),
                lang="zh",
            )
            session.add(atom)
            await session.flush()

        existing_link = await session.execute(
            select(EventKnowledgeAtom).where(
                EventKnowledgeAtom.event_id == event_id,
                EventKnowledgeAtom.atom_id == atom.id,
            )
        )
        if not existing_link.scalar():
            link = EventKnowledgeAtom(
                event_id=event_id,
                atom_id=atom.id,
                relevance=1.0,
                position=len(analysis.get("knowledge_atoms", [])),
            )
            session.add(link)


async def _save_causal_chain(session: AsyncSession, event_id: str, analysis: dict):
    """存储因果链分析结果"""
    # 删除旧节点（级联删除 links）
    old_nodes = await session.execute(
        select(CausalNode).where(CausalNode.event_id == event_id)
    )
    for node in old_nodes.scalars().all():
        await session.delete(node)

    # 创建新节点
    node_id_map = {}
    for node_data in analysis.get("nodes", []):
        node = CausalNode(
            event_id=event_id,
            node_type=node_data["node_type"],
            title=node_data["title"],
            description=node_data.get("description"),
            probability=node_data.get("probability"),
            impact_level=node_data.get("impact_level"),
            time_horizon=node_data.get("time_horizon"),
            entities=node_data.get("entities"),
            confidence=node_data.get("confidence", 0.8),
        )
        session.add(node)
        await session.flush()
        node_id_map[node_data["id"]] = node.id

    # 创建关系
    for link_data in analysis.get("links", []):
        source_id = node_id_map.get(link_data["source"])
        target_id = node_id_map.get(link_data["target"])
        if source_id and target_id:
            link = CausalLink(
                source_node_id=source_id,
                target_node_id=target_id,
                link_type=link_data.get("link_type", "causes"),
                strength=link_data.get("strength", 1.0),
                description=link_data.get("description"),
            )
            session.add(link)


async def _save_representation(session: AsyncSession, event_id: str, repr_result: dict):
    """存储事件表征"""
    surface = repr_result.get("surface", {})
    structural = repr_result.get("structural", {})
    abstract = repr_result.get("abstract", {})

    existing = await session.execute(
        select(EventRepresentation).where(EventRepresentation.event_id == event_id)
    )
    er = existing.scalar_one_or_none()

    if er:
        er.surface_summary = surface.get("summary")
        er.surface_entities = surface.get("entities")
        er.surface_numbers = surface.get("numbers")
        er.causal_pattern = structural.get("causal_pattern")
        er.causal_pattern_desc = structural.get("causal_pattern_desc")
        er.decision_logic = structural.get("decision_logic")
        er.transmission_mechanism = structural.get("transmission_mechanism")
        er.constraint_conditions = structural.get("constraint_conditions")
        er.economic_principle = abstract.get("economic_principle")
        er.economic_principle_desc = abstract.get("economic_principle_desc")
        er.game_theory_structure = abstract.get("game_theory_structure")
        er.institutional_context = abstract.get("institutional_context")
        er.ai_model = repr_result.get("ai_model")
        er.ai_confidence = repr_result.get("ai_confidence")
    else:
        er = EventRepresentation(
            event_id=event_id,
            surface_summary=surface.get("summary"),
            surface_entities=surface.get("entities"),
            surface_numbers=surface.get("numbers"),
            causal_pattern=structural.get("causal_pattern"),
            causal_pattern_desc=structural.get("causal_pattern_desc"),
            decision_logic=structural.get("decision_logic"),
            transmission_mechanism=structural.get("transmission_mechanism"),
            constraint_conditions=structural.get("constraint_conditions"),
            economic_principle=abstract.get("economic_principle"),
            economic_principle_desc=abstract.get("economic_principle_desc"),
            game_theory_structure=abstract.get("game_theory_structure"),
            institutional_context=abstract.get("institutional_context"),
            ai_model=repr_result.get("ai_model"),
            ai_confidence=repr_result.get("ai_confidence"),
        )
        session.add(er)


async def _find_and_save_analogies(
    session: AsyncSession,
    event_id: str,
    event_data: dict,
    repr_result: dict,
    ai_client: DeepSeekClient,
) -> int:
    """查找并存储历史类比"""
    structural = repr_result.get("structural", {})
    abstract = repr_result.get("abstract", {})

    # 查找候选事件
    candidates_query = (
        select(EventRepresentation)
        .where(EventRepresentation.event_id != event_id)
        .where(
            (EventRepresentation.causal_pattern == structural.get("causal_pattern"))
            | (EventRepresentation.economic_principle == abstract.get("economic_principle"))
        )
        .limit(10)
    )
    candidates_result = await session.execute(candidates_query)
    candidates = candidates_result.scalars().all()

    if not candidates:
        return 0

    # 排除已有的类比
    candidate_ids = [c.event_id for c in candidates]
    existing_result = await session.execute(
        select(HistoricalAnalogy.target_event_id).where(
            HistoricalAnalogy.source_event_id == event_id,
            HistoricalAnalogy.target_event_id.in_(candidate_ids),
        )
    )
    existing_targets = {row[0] for row in existing_result.fetchall()}

    analogy_count = 0
    for candidate in candidates:
        if candidate.event_id in existing_targets:
            continue

        # 规则预筛选
        rule_scores = compute_structural_similarity(
            repr_result,
            {
                "structural": {
                    "causal_pattern": candidate.causal_pattern,
                    "constraint_conditions": candidate.constraint_conditions or [],
                },
                "abstract": {
                    "economic_principle": candidate.economic_principle,
                },
            },
        )
        if rule_scores["overall"] < 0.3:
            continue

        # AI 深度类比
        source_data = {
            "title": event_data["title"],
            "causal_pattern_desc": structural.get("causal_pattern_desc"),
            "decision_logic": structural.get("decision_logic"),
            "transmission_mechanism": structural.get("transmission_mechanism"),
            "economic_principle_desc": abstract.get("economic_principle_desc"),
        }
        target_data = {
            "title": candidate.surface_summary,
            "causal_pattern_desc": candidate.causal_pattern_desc,
            "decision_logic": candidate.decision_logic,
            "transmission_mechanism": candidate.transmission_mechanism,
            "economic_principle_desc": candidate.economic_principle_desc,
        }

        analogy_result = await analyze_analogy(source_data, target_data, ai_client)
        if not analogy_result:
            continue

        analogy = HistoricalAnalogy(
            source_event_id=event_id,
            target_event_id=candidate.event_id,
            causal_similarity=analogy_result.get("causal_similarity"),
            decision_similarity=analogy_result.get("decision_similarity"),
            constraint_similarity=analogy_result.get("constraint_similarity"),
            mechanism_similarity=analogy_result.get("mechanism_similarity"),
            game_similarity=analogy_result.get("game_similarity"),
            overall_similarity=analogy_result.get("overall_similarity"),
            analogy_type=analogy_result.get("analogy_type"),
            analogy_summary=analogy_result.get("analogy_summary"),
            key_insight=analogy_result.get("key_insight"),
            lessons_learned=analogy_result.get("lessons_learned"),
            surface_differences=analogy_result.get("surface_differences"),
            structural_differences=analogy_result.get("structural_differences"),
            confidence=analogy_result.get("confidence"),
            ai_model=analogy_result.get("ai_model"),
        )
        session.add(analogy)
        analogy_count += 1

    return analogy_count


async def _save_scenarios(session: AsyncSession, event_id: str, analysis: dict):
    """存储情景推演结果"""
    existing = await session.execute(
        select(EventScenario).where(EventScenario.event_id == event_id)
    )
    es = existing.scalar_one_or_none()

    if es:
        es.key_variables = analysis.get("key_variables")
        es.observation_signals = analysis.get("observation_signals")
        es.scenarios = analysis.get("scenarios")
        es.thinking_questions = analysis.get("thinking_questions")
        es.ai_model = analysis.get("ai_model")
        es.ai_confidence = analysis.get("ai_confidence")
    else:
        es = EventScenario(
            event_id=event_id,
            key_variables=analysis.get("key_variables"),
            observation_signals=analysis.get("observation_signals"),
            scenarios=analysis.get("scenarios"),
            thinking_questions=analysis.get("thinking_questions"),
            ai_model=analysis.get("ai_model"),
            ai_confidence=analysis.get("ai_confidence"),
        )
        session.add(es)
