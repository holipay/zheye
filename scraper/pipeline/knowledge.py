"""
知识分析模块
为事件生成知识框架，识别知识缺口，补充背景知识

P0 功能：
1. 知识缺口识别 - 判断理解事件需要哪些前置知识
2. 背景补充 - 从知识库检索或AI生成背景知识
"""

import json
import logging
from datetime import datetime
from typing import Optional

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


def build_analysis_prompt(title: str, description: str, category: str, articles: list) -> str:
    """构建知识分析提示词"""
    article_summaries = []
    for i, article in enumerate(articles[:5], 1):
        summary = article.get('summary', article.get('title', ''))
        article_summaries.append(f"{i}. {article.get('title', '')} - {summary[:200]}")
    
    return KNOWLEDGE_ANALYSIS_PROMPT.format(
        title=title,
        description=description or "无",
        category=category,
        article_summaries="\n".join(article_summaries) if article_summaries else "无相关文章"
    )


def parse_ai_response(response: str) -> Optional[dict]:
    """解析AI返回的JSON"""
    try:
        # 尝试提取JSON块
        if "```json" in response:
            start = response.index("```json") + 7
            end = response.index("```", start)
            json_str = response[start:end].strip()
        elif "```" in response:
            start = response.index("```") + 3
            end = response.index("```", start)
            json_str = response[start:end].strip()
        else:
            json_str = response.strip()
        
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"解析AI响应失败: {e}")
        return None


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
    if not ai_client or not ai_client.enabled:
        logger.warning("AI 未启用，跳过知识分析")
        return None
    
    prompt = build_analysis_prompt(
        title=event.get('title', ''),
        description=event.get('description', ''),
        category=event.get('category', ''),
        articles=articles
    )
    
    try:
        response = ai_client._call_api(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # 低温度，更确定性的输出
            max_tokens=3000
        )
        
        if not response:
            return None
        
        result = parse_ai_response(response)
        if result:
            result['ai_model'] = 'deepseek-chat'
            result['ai_confidence'] = 0.8  # 可以后续根据响应质量调整
        
        return result
        
    except Exception as e:
        logger.error(f"知识分析失败: {e}")
        return None


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
