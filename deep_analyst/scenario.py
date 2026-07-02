"""
情景推演模块
提供思考框架，而非预测结论

核心理念：
- 价值不在于预测准确，而在于启发审视
- 识别关键变量，提供观察框架
- 赋能用户自己的判断
"""

import logging
from typing import Optional

from deep_analyst.utils import parse_ai_response, format_article_summaries, ai_analyze
from deep_analyst.schemas import ScenarioAnalysisSchema

logger = logging.getLogger(__name__)


# ============================================================
# AI 提示词：情景推演框架
# ============================================================

SCENARIO_ANALYSIS_PROMPT = """你是一个金融事件分析框架设计师。为用户提供"该关注什么"的思考框架，而不是预测未来。

## 事件
标题：{title}
描述：{description}
分类：{category}
因果模式：{causal_pattern}
文章摘要：{article_summaries}

## 输出 JSON
```json
{{
    "key_variables": [{{"name": "...", "why_important": "...", "current_status": "...", "data_source": "..."}}],
    "observation_signals": [{{"signal": "...", "what_to_watch": "...", "frequency": "日/周/月", "source": "..."}}],
    "scenarios": [{{
        "name": "情景名称",
        "description": "50-100字描述",
        "trigger_conditions": ["具体可判断的条件"],
        "observation_cues": ["什么信号表明走向此情景"],
        "implications": "如果发生意味着什么"
    }}],
    "thinking_questions": [{{"question": "...", "purpose": "...", "perspective": "投资者/政策制定者/普通民众/企业主"}}],
    "framework_summary": "2-3句核心逻辑"
}}
```

## 要求
- 关键变量≤5个，聚焦真正重要的
- 观察信号具体可操作
- 情景重在触发条件，不给概率
- 思考问题引发深度思考（非yes/no）
- 语言：中文"""


def build_scenario_prompt(title: str, description: str, category: str, causal_pattern: str, articles: list) -> str:
    """构建情景推演提示词"""
    return SCENARIO_ANALYSIS_PROMPT.format(
        title=title,
        description=description or "无",
        category=category,
        causal_pattern=causal_pattern or "未识别",
        article_summaries=format_article_summaries(articles)
    )


async def analyze_scenarios(event: dict, articles: list, ai_client, causal_pattern: str = None) -> Optional[dict]:
    """
    生成情景推演框架
    
    Args:
        event: 事件信息
        articles: 相关文章
        ai_client: AI客户端
        causal_pattern: 因果模式（来自表征提取）
    
    Returns:
        情景推演框架
    """
    prompt = build_scenario_prompt(
        title=event.get('title', ''),
        description=event.get('description', ''),
        category=event.get('category', ''),
        causal_pattern=causal_pattern,
        articles=articles
    )
    
    return await ai_analyze(
        prompt=prompt,
        ai_client=ai_client,
        temperature=0.4,
        max_tokens=3000,
        schema=ScenarioAnalysisSchema,
        function_name="analyze_scenarios"
    )
