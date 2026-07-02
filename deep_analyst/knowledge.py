"""
知识分析模块
为事件生成知识框架，识别知识缺口，补充背景知识，构建因果链

P0 功能：
1. 知识缺口识别 - 判断理解事件需要哪些前置知识
2. 背景补充 - 从知识库检索或AI生成背景知识

P1 功能：
3. 因果链构建 - 多层次因果分析

知识原子复用：
- 分析前先检索已有知识原子（同 category 或 entity 重叠）
- 将已有原子注入 prompt，让 AI 只生成新知识
- 减少重复 AI 调用，保持知识一致性

增强功能：
- 语义相似度匹配（TF-IDF）
- 跨 category 复用
- 复用统计追踪
- 质量衰减机制
- 知识原子版本更新
- 冲突检测
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Set
from sqlalchemy import select, or_, func, update, and_, Float
from sqlalchemy.ext.asyncio import AsyncSession

from deep_analyst.utils import parse_ai_response, format_article_summaries, ai_analyze
from deep_analyst.schemas import KnowledgeAnalysisSchema, CausalChainSchema, KnowledgeAndCausalSchema
from deep_analyst.models.knowledge import KnowledgeAtom, EventKnowledgeAtom

logger = logging.getLogger(__name__)


# ============================================================
# Category 关联映射
# ============================================================

# 默认的 category 关联关系（如果数据库表不存在时使用）
DEFAULT_CATEGORY_RELATIONS = {
    "央行与利率": {"宏观经济": 0.8, "股市与市场": 0.6},
    "宏观经济": {"央行与利率": 0.8, "大宗商品与能源": 0.5},
    "股市与市场": {"科技与企业": 0.6, "央行与利率": 0.6},
    "大宗商品与能源": {"宏观经济": 0.5, "国际财经": 0.4},
    "科技与企业": {"股市与市场": 0.6},
    "国际财经": {"宏观经济": 0.4, "大宗商品与能源": 0.4},
}

# ============================================================
# 语义相似度工具
# ============================================================

def _get_tfidf_similarity(text: str, atom_contents: List[str]) -> List[float]:
    """
    计算文本与知识原子内容的TF-IDF相似度
    
    Args:
        text: 查询文本
        atom_contents: 知识原子内容列表
    
    Returns:
        相似度分数列表
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        if not atom_contents:
            return []
        
        vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(2, 4),
            max_features=5000,
            dtype=np.float32,
        )
        
        # 将查询文本和所有内容一起fit
        all_texts = [text] + atom_contents
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        
        # 计算查询文本与每个内容的相似度
        query_vector = tfidf_matrix[0:1]
        content_vectors = tfidf_matrix[1:]
        similarities = cosine_similarity(query_vector, content_vectors)[0]
        
        return similarities.tolist()
        
    except Exception as e:
        logger.warning(f"TF-IDF 相似度计算失败: {e}")
        return [0.0] * len(atom_contents)


# ============================================================
# AI 提示词模板
# ============================================================

KNOWLEDGE_ANALYSIS_PROMPT = """你是一个金融新闻知识分析师。分析新闻事件，识别读者理解事件必需的背景知识。

## 事件
标题：{title}
描述：{description}
分类：{category}
文章摘要：{article_summaries}

## 输出 JSON
```json
{{
    "background_summary": "2-3句核心背景",
    "knowledge_gaps": [{{"topic": "...", "why_needed": "...", "priority": "high/medium/low"}}],
    "causal_chain": [{{"step": 1, "cause": "...", "effect": "...", "evidence": "..."}}],
    "key_concepts": [{{"concept": "...", "definition": "...", "relevance": "..."}}],
    "knowledge_atoms": [{{"atom_type": "background/history/definition/mechanism/context", "title": "...", "content": "100-200字", "entities": [], "keywords": []}}]
}}
```

## 要求
- knowledge_gaps: 识别读者必需但可能不知道的知识
- knowledge_atoms: 面向金融知识有限的读者，简洁易懂
- 语言：中文，不要编造事实"""


# 带已有知识原子的提示词（复用模式）
KNOWLEDGE_ANALYSIS_WITH_EXISTING_PROMPT = """你是一个金融新闻知识分析师。分析新闻事件，识别读者理解事件必需的背景知识。

## 事件
标题：{title}
描述：{description}
分类：{category}
文章摘要：{article_summaries}

## 已有知识原子（不需要重复）
{existing_atoms_text}

**重要**：knowledge_atoms 只包含已有知识未覆盖的新知识。

## 输出 JSON
```json
{{
    "background_summary": "2-3句核心背景",
    "knowledge_gaps": [{{"topic": "...", "why_needed": "...", "priority": "high/medium/low"}}],
    "causal_chain": [{{"step": 1, "cause": "...", "effect": "...", "evidence": "..."}}],
    "key_concepts": [{{"concept": "...", "definition": "...", "relevance": "..."}}],
    "knowledge_atoms": [{{"atom_type": "background/history/definition/mechanism/context", "title": "新知识", "content": "100-200字", "entities": [], "keywords": []}}],
    "reused_atom_ids": [1, 2, 3]
}}
```

## 要求
- knowledge_atoms: 只包含新知识，reused_atom_ids 填写复用的已有原子 ID
- 语言：中文，不要编造事实"""


async def find_relevant_atoms(
    session: AsyncSession,
    category: str,
    entities: List[str] = None,
    keywords: List[str] = None,
    event_description: str = None,
    lang: str = "zh",
    limit: int = 20,
    min_quality: float = 0.3,
) -> List[dict]:
    """
    查找与事件相关的已有知识原子

    匹配策略：
    1. 同 category 的原子
    2. 相关 category 的原子（跨category复用）
    3. entities 有重叠的原子（JSONB 数组交集）
    4. keywords 有重叠的原子（JSONB 数组交集）
    5. 语义相似度匹配（TF-IDF）

    Args:
        session: 数据库会话
        category: 事件分类
        entities: 事件涉及的实体列表
        keywords: 事件涉及的关键词列表
        event_description: 事件描述（用于语义匹配）
        lang: 语言
        limit: 最多返回数量
        min_quality: 最低质量评分

    Returns:
        匹配的知识原子列表 [{id, atom_type, title, content, entities, keywords, relevance_score, quality_score}]
    """
    # 必须同时满足的条件
    base_conditions = [
        KnowledgeAtom.lang == lang,
        KnowledgeAtom.quality_score >= min_quality,
    ]

    # 获取相关 category 列表
    related_categories = _get_related_categories(category)
    all_categories = [category] + related_categories if category else []

    # category 或 entity 重叠的可选条件（至少满足一个）
    filter_conditions = []
    if all_categories:
        filter_conditions.append(KnowledgeAtom.category.in_(all_categories))
    if entities:
        for entity in entities[:5]:
            filter_conditions.append(
                KnowledgeAtom.entities.op("@>")(func.json_build_array(entity))
            )

    if not filter_conditions:
        return []

    from sqlalchemy import and_
    stmt = (
        select(KnowledgeAtom)
        .where(and_(*base_conditions, or_(*filter_conditions)))
        .order_by(KnowledgeAtom.quality_score.desc(), KnowledgeAtom.created_at.desc())
        .limit(limit * 3)
    )

    result = await session.execute(stmt)
    atoms = result.scalars().all()

    if not atoms:
        return []

    # 计算相关度分数
    scored_atoms = []
    seen_ids = set()

    # 准备语义相似度计算
    atom_contents = []
    atom_list = []
    for atom in atoms:
        if atom.id in seen_ids:
            continue
        seen_ids.add(atom.id)
        atom_list.append(atom)
        atom_contents.append(f"{atom.title} {atom.content}")

    # 计算语义相似度
    semantic_scores = []
    if event_description and atom_contents:
        semantic_scores = _get_tfidf_similarity(event_description, atom_contents)

    for i, atom in enumerate(atom_list):
        score = 0.0

        # 同 category +0.3（相关category按比例衰减）
        if category and atom.category == category:
            score += 0.3
        elif category and atom.category in related_categories:
            strength = related_categories.get(atom.category, 0.3)
            score += 0.3 * strength

        # entity 重叠
        if entities and atom.entities:
            overlap = set(entities) & set(atom.entities)
            score += min(len(overlap) * 0.2, 0.5)

        # keyword 重叠
        if keywords and atom.keywords:
            overlap = set(keywords) & set(atom.keywords)
            score += min(len(overlap) * 0.1, 0.3)

        # 语义相似度（权重0.3）
        if semantic_scores and i < len(semantic_scores):
            score += semantic_scores[i] * 0.3

        # 质量评分加成
        score *= atom.quality_score

        scored_atoms.append({
            "id": atom.id,
            "atom_type": atom.atom_type,
            "title": atom.title,
            "content": atom.content,
            "entities": atom.entities or [],
            "keywords": atom.keywords or [],
            "category": atom.category,
            "relevance_score": round(score, 3),
            "quality_score": atom.quality_score,
            "reuse_count": atom.reuse_count,
            "version": atom.version,
        })

    # 按相关度排序
    scored_atoms.sort(key=lambda x: x["relevance_score"], reverse=True)

    return scored_atoms[:limit]


def _get_related_categories(category: str) -> Dict[str, float]:
    """
    获取相关 category 及其关联强度
    
    Args:
        category: 原始分类
    
    Returns:
        相关分类字典 {category: strength}
    """
    if not category:
        return {}
    return DEFAULT_CATEGORY_RELATIONS.get(category, {})


# P1: 深度因果链分析提示词
CAUSAL_CHAIN_PROMPT = """你是一个金融事件因果分析专家。分析新闻事件的因果结构，构建多层次因果链。

## 事件
标题：{title}
描述：{description}
分类：{category}
文章摘要：{article_summaries}

## 输出 JSON
```json
{{
    "nodes": [{{"id": "node_1", "node_type": "root_cause/trigger/immediate/short_term/long_term/scenario", "title": "...", "description": "50-100字", "impact_level": "high/medium/low", "time_horizon": "immediate/days/weeks/months/years", "entities": [], "confidence": 0.8, "probability": 0.4}}],
    "links": [{{"source": "node_1", "target": "node_2", "link_type": "leads_to/triggers/causes/may_cause", "strength": 0.9}}],
    "summary": "3-5句因果逻辑总结"
}}
```

## 节点类型
- root_cause: 深层结构性因素（经济周期、政策框架）
- trigger: 直接导火索
- immediate/short_term/long_term: 按时间维度的效应
- scenario: 未来可能走向（需标注 probability）

## 要求
- 语言：中文，不要编造事实"""


def build_analysis_prompt(title: str, description: str, category: str, articles: list) -> str:
    """构建知识分析提示词"""
    return KNOWLEDGE_ANALYSIS_PROMPT.format(
        title=title,
        description=description or "无",
        category=category,
        article_summaries=format_article_summaries(articles)
    )


def build_causal_chain_prompt(title: str, description: str, category: str, articles: list) -> str:
    """构建因果链分析提示词"""
    return CAUSAL_CHAIN_PROMPT.format(
        title=title,
        description=description or "无",
        category=category,
        article_summaries=format_article_summaries(articles)
    )


async def analyze_event_knowledge(
    event: dict,
    articles: list,
    ai_client,
    existing_atoms: List[dict] = None,
) -> Optional[dict]:
    """
    分析事件的知识框架

    Args:
        event: 事件信息 {title, description, category, ...}
        articles: 相关文章列表 [{title, summary, ...}, ...]
        ai_client: AI客户端实例
        existing_atoms: 已有知识原子列表（可选，用于复用）

    Returns:
        知识框架字典，或 None
    """
    if existing_atoms:
        # 有已有原子时，使用带上下文的 prompt
        existing_text = _format_existing_atoms(existing_atoms)
        prompt = KNOWLEDGE_ANALYSIS_WITH_EXISTING_PROMPT.format(
            title=event.get('title', ''),
            description=event.get('description', ''),
            category=event.get('category', ''),
            article_summaries=format_article_summaries(articles),
            existing_atoms_text=existing_text,
        )
    else:
        prompt = KNOWLEDGE_ANALYSIS_PROMPT.format(
            title=event.get('title', ''),
            description=event.get('description', ''),
            category=event.get('category', ''),
            article_summaries=format_article_summaries(articles),
        )

    result = await ai_analyze(
        prompt=prompt,
        ai_client=ai_client,
        temperature=0.3,
        max_tokens=3000,
        schema=KnowledgeAnalysisSchema,
        function_name="analyze_event_knowledge"
    )

    # 将复用的原子 ID 附加到结果中
    if result and existing_atoms:
        reused_ids = result.get("reused_atom_ids", [])
        if reused_ids:
            result["_reused_atom_ids"] = reused_ids

    return result


def _format_existing_atoms(atoms: List[dict]) -> str:
    """将已有知识原子格式化为 prompt 文本"""
    lines = []
    for atom in atoms:
        score = atom.get("relevance_score", 0)
        if score < 0.2:
            continue  # 跳过相关度太低的
        entities_str = ", ".join(atom.get("entities", []))
        line = f"- [ID:{atom['id']}] [{atom['atom_type']}] {atom['title']}"
        if entities_str:
            line += f"（实体: {entities_str}）"
        line += f"\n  {atom['content'][:150]}..."
        lines.append(line)

    return "\n".join(lines) if lines else "无"


async def analyze_causal_chain(event: dict, articles: list, ai_client) -> Optional[dict]:
    """
    P1: 深度因果链分析
    
    Args:
        event: 事件信息
        articles: 相关文章列表
        ai_client: AI客户端实例
    
    Returns:
        因果链结构 {nodes: [...], links: [...], summary: "..."}
    """
    prompt = build_causal_chain_prompt(
        title=event.get('title', ''),
        description=event.get('description', ''),
        category=event.get('category', ''),
        articles=articles
    )
    
    return await ai_analyze(
        prompt=prompt,
        ai_client=ai_client,
        temperature=0.3,
        max_tokens=4000,
        schema=CausalChainSchema,
        function_name="analyze_causal_chain"
    )


# ============================================================
# 合并 Step 1+2: 知识框架 + 因果链
# ============================================================

KNOWLEDGE_AND_CAUSAL_PROMPT = """你是一个金融新闻知识分析师。分析以下新闻事件，同时完成：1)知识框架 2)因果链图。

## 事件
标题：{title}
描述：{description}
分类：{category}
文章摘要：{article_summaries}

## 输出 JSON
```json
{{
    "background_summary": "2-3句核心背景",
    "knowledge_gaps": [{{"topic": "...", "why_needed": "...", "priority": "high/medium/low"}}],
    "causal_chain": [{{"step": 1, "cause": "...", "effect": "...", "evidence": "..."}}],
    "key_concepts": [{{"concept": "...", "definition": "...", "relevance": "..."}}],
    "knowledge_atoms": [{{"atom_type": "background/history/definition/mechanism/context", "title": "...", "content": "100-200字", "entities": [], "keywords": []}}],
    "causal_graph": {{
        "nodes": [{{"id": "node_1", "node_type": "root_cause/trigger/immediate/short_term/long_term/scenario", "title": "...", "description": "...", "impact_level": "high/medium/low", "time_horizon": "immediate/days/weeks/months/years", "entities": [], "confidence": 0.8}}],
        "links": [{{"source": "node_1", "target": "node_2", "link_type": "leads_to/triggers/causes/may_cause", "strength": 0.9}}],
        "summary": "3-5句因果逻辑总结"
    }}
}}
```

## 节点类型
- root_cause: 深层结构性因素（经济周期、政策框架）
- trigger: 直接导火索
- immediate/short_term/long_term: 按时间维度的效应
- scenario: 未来可能走向（需标注 probability）

## 要求
- knowledge_gaps: 识别读者必需但可能不知道的知识
- knowledge_atoms: 面向金融知识有限的读者，简洁易懂
- causal_chain: 线性因果步骤；causal_graph: 完整因果网络
- 语言：中文，不要编造事实"""


KNOWLEDGE_AND_CAUSAL_WITH_EXISTING_PROMPT = """你是一个金融新闻知识分析师。分析以下事件，生成知识框架和因果链图。

## 事件
标题：{title}
描述：{description}
分类：{category}
文章摘要：{article_summaries}

## 已有知识原子（不需要重复）
{existing_atoms_text}

**重要**：knowledge_atoms 只包含已有知识未覆盖的新知识。

## 输出 JSON
```json
{{
    "background_summary": "2-3句核心背景",
    "knowledge_gaps": [{{"topic": "...", "why_needed": "...", "priority": "high/medium/low"}}],
    "causal_chain": [{{"step": 1, "cause": "...", "effect": "...", "evidence": "..."}}],
    "key_concepts": [{{"concept": "...", "definition": "...", "relevance": "..."}}],
    "knowledge_atoms": [{{"atom_type": "background/history/definition/mechanism/context", "title": "新知识", "content": "100-200字", "entities": [], "keywords": []}}],
    "reused_atom_ids": [1, 2, 3],
    "causal_graph": {{
        "nodes": [{{"id": "node_1", "node_type": "root_cause/trigger/immediate/short_term/long_term/scenario", "title": "...", "description": "...", "impact_level": "high/medium/low", "time_horizon": "immediate/days/weeks/months/years", "entities": [], "confidence": 0.8}}],
        "links": [{{"source": "node_1", "target": "node_2", "link_type": "leads_to/triggers/causes/may_cause", "strength": 0.9}}],
        "summary": "3-5句因果逻辑总结"
    }}
}}
```

## 要求
- knowledge_atoms: 只包含新知识，reused_atom_ids 填写复用的已有原子 ID
- 语言：中文，不要编造事实"""


async def analyze_event_knowledge_and_causal(
    event: dict,
    articles: list,
    ai_client,
    existing_atoms: List[dict] = None,
) -> Optional[dict]:
    """
    合并 Step 1+2: 一次调用同时分析知识框架和因果链图

    Args:
        event: 事件信息 {title, description, category, ...}
        articles: 相关文章列表 [{title, summary, ...}, ...]
        ai_client: AI客户端实例
        existing_atoms: 已有知识原子列表（可选，用于复用）

    Returns:
        包含 knowledge_framework + causal_graph 的字典，或 None
    """
    if existing_atoms:
        existing_text = _format_existing_atoms(existing_atoms)
        prompt = KNOWLEDGE_AND_CAUSAL_WITH_EXISTING_PROMPT.format(
            title=event.get('title', ''),
            description=event.get('description', ''),
            category=event.get('category', ''),
            article_summaries=format_article_summaries(articles),
            existing_atoms_text=existing_text,
        )
    else:
        prompt = KNOWLEDGE_AND_CAUSAL_PROMPT.format(
            title=event.get('title', ''),
            description=event.get('description', ''),
            category=event.get('category', ''),
            article_summaries=format_article_summaries(articles),
        )

    result = await ai_analyze(
        prompt=prompt,
        ai_client=ai_client,
        temperature=0.3,
        max_tokens=5000,
        schema=KnowledgeAndCausalSchema,
        function_name="analyze_knowledge_and_causal"
    )

    if result and existing_atoms:
        reused_ids = result.get("reused_atom_ids", [])
        if reused_ids:
            result["_reused_atom_ids"] = reused_ids

    return result


def get_knowledge_type_label(atom_type: str, lang: str = 'zh') -> str:
    """获取知识类型的显示标签"""
    labels = {
        'zh': {
            'background': '背景知识',
            'history': '历史参照',
            'definition': '概念解释',
            'mechanism': '运作机制',
            'context': '相关背景',
        },
        'en': {
            'background': 'Background',
            'history': 'Historical Context',
            'definition': 'Definition',
            'mechanism': 'Mechanism',
            'context': 'Context',
        }
    }
    return labels.get(lang, labels['zh']).get(atom_type, atom_type)


def get_link_type_label(link_type: str, lang: str = 'zh') -> str:
    """获取关系类型的显示标签"""
    labels = {
        'zh': {
            'causes': '导致',
            'leads_to': '引向',
            'triggers': '触发',
            'enables': '促成',
            'may_cause': '可能导致',
        },
        'en': {
            'causes': 'causes',
            'leads_to': 'leads to',
            'triggers': 'triggers',
            'enables': 'enables',
            'may_cause': 'may cause',
        }
    }
    return labels.get(lang, labels['zh']).get(link_type, link_type)


# ============================================================
# 复用统计更新
# ============================================================

async def update_reuse_stats(
    session: AsyncSession,
    atom_ids: List[int],
) -> int:
    """
    更新知识原子的复用统计
    
    Args:
        session: 数据库会话
        atom_ids: 被复用的原子ID列表
    
    Returns:
        更新的原子数量
    """
    if not atom_ids:
        return 0
    
    now = datetime.now(timezone.utc)
    
    # 批量更新复用次数和最后复用时间
    stmt = (
        update(KnowledgeAtom)
        .where(KnowledgeAtom.id.in_(atom_ids))
        .values(
            reuse_count=KnowledgeAtom.reuse_count + 1,
            last_reused_at=now,
        )
    )
    
    result = await session.execute(stmt)
    return result.rowcount


# ============================================================
# 知识原子版本更新
# ============================================================

async def update_knowledge_atom(
    session: AsyncSession,
    atom_id: int,
    new_content: str = None,
    new_title: str = None,
    reason: str = None,
) -> Optional[KnowledgeAtom]:
    """
    更新知识原子（创建新版本）
    
    Args:
        session: 数据库会话
        atom_id: 原子ID
        new_content: 新内容
        new_title: 新标题
        reason: 更新原因
    
    Returns:
        新版本的原子，或None
    """
    # 获取原原子
    atom = await session.get(KnowledgeAtom, atom_id)
    if not atom:
        return None
    
    # 创建新版本
    new_atom = KnowledgeAtom(
        atom_type=atom.atom_type,
        title=new_title or atom.title,
        content=new_content or atom.content,
        category=atom.category,
        entities=atom.entities,
        keywords=atom.keywords,
        source_article_id=atom.source_article_id,
        confidence=atom.confidence,
        lang=atom.lang,
        version=atom.version + 1,
        previous_version_id=atom.id,
        reuse_count=0,  # 新版本复用次数重置
        quality_score=1.0,  # 新版本质量重置
    )
    
    session.add(new_atom)
    await session.flush()  # 获取新ID
    
    # 更新关联表，指向新版本
    stmt = (
        update(EventKnowledgeAtom)
        .where(EventKnowledgeAtom.atom_id == atom_id)
        .values(atom_id=new_atom.id)
    )
    await session.execute(stmt)
    
    return new_atom


# ============================================================
# 冲突检测
# ============================================================

async def detect_conflicts(
    session: AsyncSession,
    new_atoms: List[dict],
    existing_atoms: List[dict],
) -> List[dict]:
    """
    检测新知识原子与已有原子的潜在冲突
    
    Args:
        session: 数据库会话
        new_atoms: 新生成的原子列表
        existing_atoms: 已有的原子列表
    
    Returns:
        冲突列表 [{new_atom, existing_atom, conflict_type, description}]
    """
    conflicts = []
    
    for new_atom in new_atoms:
        new_title = new_atom.get("title", "").lower()
        new_content = new_atom.get("content", "").lower()
        
        for exist_atom in existing_atoms:
            exist_title = exist_atom.get("title", "").lower()
            exist_content = exist_atom.get("content", "").lower()
            
            # 标题高度相似但内容不同 -> 可能冲突
            title_sim = _simple_similarity(new_title, exist_title)
            if title_sim > 0.7:
                content_sim = _simple_similarity(new_content, exist_content)
                if content_sim < 0.5:
                    conflicts.append({
                        "new_atom": new_atom,
                        "existing_atom": exist_atom,
                        "conflict_type": "content_mismatch",
                        "description": f"标题相似但内容不同: '{new_atom.get('title')}' vs '{exist_atom.get('title')}'",
                        "title_similarity": title_sim,
                        "content_similarity": content_sim,
                    })
            
            # 检查否定词冲突
            if _has_negation_conflict(new_content, exist_content):
                conflicts.append({
                    "new_atom": new_atom,
                    "existing_atom": exist_atom,
                    "conflict_type": "negation",
                    "description": f"可能存在否定冲突: '{new_atom.get('title')}'",
                })
    
    return conflicts


def _simple_similarity(text1: str, text2: str) -> float:
    """简单的文本相似度计算（基于字符重叠）"""
    if not text1 or not text2:
        return 0.0
    
    set1 = set(text1)
    set2 = set(text2)
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def _has_negation_conflict(text1: str, text2: str) -> bool:
    """检查两个文本是否存在否定冲突"""
    negation_words = ["不", "没有", "并非", "不是", "无", "未"]
    
    for word in negation_words:
        # 一个有否定词，另一个没有
        if (word in text1 and word not in text2) or (word not in text1 and word in text2):
            # 检查其他内容是否相似
            common_chars = set(text1) & set(text2)
            if len(common_chars) > 10:  # 有一定相似度
                return True
    
    return False


# ============================================================
# 质量衰减
# ============================================================

async def apply_quality_decay(
    session: AsyncSession,
    decay_rate: float = 0.01,
    min_quality: float = 0.3,
) -> int:
    """
    应用质量衰减（定期调用）
    
    Args:
        session: 数据库会话
        decay_rate: 每月衰减率
        min_quality: 最低质量分
    
    Returns:
        更新的原子数量
    """
    # 计算衰减后的质量分
    # 公式: quality = max(min_quality, min(1.0, (0.5 + 0.5 * min(reuse_count/10, 1)) * exp(-decay * months)))
    months_since_reuse = func.extract('epoch', func.now() - func.coalesce(KnowledgeAtom.last_reused_at, KnowledgeAtom.created_at)) / (30 * 24 * 3600)
    
    new_quality = func.greatest(
        min_quality,
        func.least(
            1.0,
            (0.5 + 0.5 * func.least(KnowledgeAtom.reuse_count.cast(Float) / 10, 1.0))
            * func.exp(-decay_rate * months_since_reuse)
        )
    )
    
    stmt = (
        update(KnowledgeAtom)
        .where(KnowledgeAtom.quality_score > min_quality)
        .values(quality_score=new_quality)
    )
    
    result = await session.execute(stmt)
    return result.rowcount


# ============================================================
# 复用统计API
# ============================================================

async def get_reuse_statistics(
    session: AsyncSession,
    limit: int = 20,
) -> Dict:
    """
    获取知识原子复用统计
    
    Args:
        session: 数据库会话
        limit: 返回的热门原子数量
    
    Returns:
        统计数据字典
    """
    # 总原子数
    total_query = select(func.count(KnowledgeAtom.id))
    total_result = await session.execute(total_query)
    total_atoms = total_result.scalar()
    
    # 被复用的原子数
    reused_query = select(func.count(KnowledgeAtom.id)).where(KnowledgeAtom.reuse_count > 0)
    reused_result = await session.execute(reused_query)
    reused_atoms = reused_result.scalar()
    
    # 平均复用次数
    avg_query = select(func.avg(KnowledgeAtom.reuse_count)).where(KnowledgeAtom.reuse_count > 0)
    avg_result = await session.execute(avg_query)
    avg_reuse = avg_result.scalar() or 0
    
    # 热门原子
    hot_query = (
        select(KnowledgeAtom)
        .where(KnowledgeAtom.reuse_count > 0)
        .order_by(KnowledgeAtom.reuse_count.desc())
        .limit(limit)
    )
    hot_result = await session.execute(hot_query)
    hot_atoms = [
        {
            "id": atom.id,
            "title": atom.title,
            "category": atom.category,
            "reuse_count": atom.reuse_count,
            "quality_score": atom.quality_score,
            "last_reused_at": atom.last_reused_at.isoformat() if atom.last_reused_at else None,
        }
        for atom in hot_result.scalars().all()
    ]
    
    # 按category统计
    category_query = (
        select(KnowledgeAtom.category, func.count(KnowledgeAtom.id), func.avg(KnowledgeAtom.reuse_count))
        .group_by(KnowledgeAtom.category)
    )
    category_result = await session.execute(category_query)
    category_stats = [
        {
            "category": row[0],
            "count": row[1],
            "avg_reuse": round(float(row[2] or 0), 2),
        }
        for row in category_result.fetchall()
    ]
    
    return {
        "total_atoms": total_atoms,
        "reused_atoms": reused_atoms,
        "reuse_rate": round(reused_atoms / total_atoms * 100, 1) if total_atoms > 0 else 0,
        "avg_reuse_count": round(float(avg_reuse), 2),
        "hot_atoms": hot_atoms,
        "category_stats": category_stats,
    }
