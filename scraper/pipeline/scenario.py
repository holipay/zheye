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

from scraper.pipeline.utils import parse_ai_response, format_article_summaries, ai_analyze
from models.schemas import ScenarioAnalysisSchema

logger = logging.getLogger(__name__)


# ============================================================
# AI 提示词：情景推演框架
# ============================================================

SCENARIO_ANALYSIS_PROMPT = """你是一个金融事件分析框架设计师。你的任务不是预测未来会怎样，而是为用户提供一个"该关注什么"的思考框架。

## 事件信息
标题：{title}
描述：{description}
分类：{category}
因果模式：{causal_pattern}
相关文章摘要：
{article_summaries}

## 设计原则

你的目标是帮助用户**自己思考**，而不是告诉他们答案。好的框架应该：
1. 识别真正决定走向的关键变量（不是所有因素都同等重要）
2. 提供可观察的早期信号（用户可以自己跟踪）
3. 展示不同情景的触发条件（什么条件下会走向哪个方向）
4. 引导用户从不同角度审视事件

## 输出要求

请输出严格的 JSON 格式：

```json
{{
    "key_variables": [
        {{
            "name": "变量名称（如：通胀走势）",
            "why_important": "为什么这个变量是关键（它如何决定走向）",
            "current_status": "当前状态（基于文章信息）",
            "data_source": "如何获取这个数据（数据来源、发布频率）"
        }}
    ],
    
    "observation_signals": [
        {{
            "signal": "可观察的信号（如：CPI环比变化）",
            "what_to_watch": "具体观察什么",
            "frequency": "观察频率（日/周/月）",
            "source": "数据来源"
        }}
    ],
    
    "scenarios": [
        {{
            "name": "情景名称（如：软着陆）",
            "description": "情景描述（50-100字）",
            "trigger_conditions": [
                "触发条件1：具体、可判断的条件",
                "触发条件2：..."
            ],
            "observation_cues": [
                "观察线索1：什么信号表明正在走向这个情景",
                "观察线索2：..."
            ],
            "implications": "如果这个情景发生，意味着什么"
        }}
    ],
    
    "thinking_questions": [
        {{
            "question": "引导性问题",
            "purpose": "这个问题的目的（引导用户从什么角度思考）",
            "perspective": "思考视角（投资者/政策制定者/普通民众/企业主）"
        }}
    ],
    
    "framework_summary": "用2-3句话总结这个思考框架的核心逻辑"
}}
```

## 注意事项
1. 关键变量不超过5个，要聚焦真正重要的
2. 观察信号要具体、可操作，不是模糊的描述
3. 情景框架重在"条件"，不是"概率"——不要给概率
4. 思考问题要能引发真正的思考，不是yes/no问题
5. 不要预测，要赋能
6. 语言：中文"""


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
