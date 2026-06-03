"""
知识分析模块
为事件生成知识框架，识别知识缺口，补充背景知识，构建因果链

P0 功能：
1. 知识缺口识别 - 判断理解事件需要哪些前置知识
2. 背景补充 - 从知识库检索或AI生成背景知识

P1 功能：
3. 因果链构建 - 多层次因果分析
"""

import json
import logging
from datetime import datetime
from typing import Optional, List

from scraper.pipeline.utils import parse_ai_response, format_article_summaries, ai_analyze
from models.schemas import KnowledgeAnalysisSchema, CausalChainSchema

logger = logging.getLogger(__name__)


# ============================================================
# AI 提示词模板
# ============================================================

KNOWLEDGE_ANALYSIS_PROMPT = """你是一个金融新闻知识分析师。你的任务是分析一个新闻事件，识别出"要真正理解这件事，读者需要知道的关键背景知识"。

## 事件信息
标题：{title}
描述：{description}
分类：{category}
相关文章摘要：
{article_summaries}

## 你的任务

请分析这个事件，生成结构化的知识框架。输出必须是严格的 JSON 格式：

```json
{{
    "background_summary": "用2-3句话概述这个事件的核心背景（为什么发生）",
    
    "knowledge_gaps": [
        {{
            "topic": "知识缺口主题（如'什么是基点'、'该国通胀历史'）",
            "why_needed": "为什么理解这个事件需要知道这个",
            "priority": "high/medium/low"
        }}
    ],
    
    "causal_chain": [
        {{
            "step": 1,
            "cause": "原因/触发因素",
            "effect": "导致的结果",
            "evidence": "支撑证据（来自文章）"
        }}
    ],
    
    "key_concepts": [
        {{
            "concept": "关键概念名称",
            "definition": "简明定义",
            "relevance": "与事件的关联"
        }}
    ],
    
    "knowledge_atoms": [
        {{
            "atom_type": "background/history/definition/mechanism/context",
            "title": "知识标题",
            "content": "知识内容（100-200字，面向金融知识有限的读者）",
            "entities": ["涉及的实体"],
            "keywords": ["相关关键词"]
        }}
    ]
}}
```

## 注意事项
1. knowledge_gaps 应该识别读者可能不知道但理解事件必需的知识
2. knowledge_atoms 应该提供简洁、易懂的背景知识
3. causal_chain 应该清晰展示因果逻辑
4. 语言：中文
5. 不要编造事实，如果不确定，标注 confidence 较低"""


# P1: 深度因果链分析提示词
CAUSAL_CHAIN_PROMPT = """你是一个金融事件因果分析专家。你的任务是深入分析一个新闻事件的因果结构，构建多层次的因果链。

## 事件信息
标题：{title}
描述：{description}
分类：{category}
相关文章摘要：
{article_summaries}

## 因果链结构

请分析这个事件的完整因果结构，从根源到未来走向。输出必须是严格的 JSON 格式：

```json
{{
    "nodes": [
        {{
            "id": "node_1",
            "node_type": "root_cause",
            "title": "根本原因标题",
            "description": "详细描述（50-100字）",
            "impact_level": "high/medium/low",
            "time_horizon": "years",
            "entities": ["涉及实体"],
            "confidence": 0.9
        }},
        {{
            "id": "node_2",
            "node_type": "trigger",
            "title": "触发因素标题",
            "description": "详细描述",
            "impact_level": "high",
            "time_horizon": "immediate",
            "entities": [],
            "confidence": 0.95
        }},
        {{
            "id": "node_3",
            "node_type": "immediate",
            "title": "即时影响标题",
            "description": "详细描述",
            "impact_level": "high",
            "time_horizon": "immediate",
            "entities": [],
            "confidence": 0.9
        }},
        {{
            "id": "node_4",
            "node_type": "short_term",
            "title": "短期效应标题",
            "description": "详细描述",
            "impact_level": "medium",
            "time_horizon": "weeks",
            "entities": [],
            "confidence": 0.8
        }},
        {{
            "id": "node_5",
            "node_type": "long_term",
            "title": "长期走向标题",
            "description": "详细描述",
            "impact_level": "medium",
            "time_horizon": "months",
            "entities": [],
            "confidence": 0.7
        }},
        {{
            "id": "node_6",
            "node_type": "scenario",
            "title": "可能情景A",
            "description": "情景描述",
            "probability": 0.4,
            "impact_level": "high",
            "time_horizon": "months",
            "entities": [],
            "confidence": 0.6
        }}
    ],
    "links": [
        {{"source": "node_1", "target": "node_2", "link_type": "leads_to", "strength": 0.9}},
        {{"source": "node_2", "target": "node_3", "link_type": "triggers", "strength": 1.0}},
        {{"source": "node_3", "target": "node_4", "link_type": "causes", "strength": 0.8}},
        {{"source": "node_4", "target": "node_5", "link_type": "leads_to", "strength": 0.7}},
        {{"source": "node_4", "target": "node_6", "link_type": "may_cause", "strength": 0.4}}
    ],
    "summary": "用3-5句话总结整个因果链的逻辑"
}}
```

## 节点类型说明
- root_cause: 根本原因（深层结构性因素，如经济周期、政策框架）
- trigger: 触发因素（直接导致事件发生的导火索）
- immediate: 即时影响（事件发生后的直接后果）
- short_term: 短期效应（数天到数周内的影响）
- long_term: 长期走向（数月到数年的影响）
- scenario: 可能情景（未来可能发生的不同走向，需标注 probability）

## 时间维度
- immediate: 立即
- days: 数天
- weeks: 数周
- months: 数月
- years: 数年

## 注意事项
1. 根本原因应该是深层的结构性因素，不是表面现象
2. 每个节点都需要有明确的因果逻辑
3. 情景节点需要估算概率
4. 语言：中文
5. 不要编造事实，如果不确定，标注 confidence 较低"""


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


async def analyze_event_knowledge(event: dict, articles: list, ai_client) -> Optional[dict]:
    """
    分析事件的知识框架
    
    Args:
        event: 事件信息 {title, description, category, ...}
        articles: 相关文章列表 [{title, summary, ...}, ...]
        ai_client: AI客户端实例
    
    Returns:
        知识框架字典，或 None
    """
    prompt = build_analysis_prompt(
        title=event.get('title', ''),
        description=event.get('description', ''),
        category=event.get('category', ''),
        articles=articles
    )
    
    return await ai_analyze(
        prompt=prompt,
        ai_client=ai_client,
        temperature=0.3,
        max_tokens=3000,
        schema=KnowledgeAnalysisSchema,
        function_name="analyze_event_knowledge"
    )


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
