"""
历史类比检索模块
多层表征提取 + 结构化匹配

核心思想：
- 表面层：具体事实（实体、数字、时间）
- 结构层：因果模式、决策逻辑、传导机制
- 抽象层：经济学原理、博弈结构

匹配原则：
- 找"结构相似但表面不同"的历史事件
- 不是找最相似的文本，而是找同构的因果模式
"""

import json
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================
# AI 提示词：事件多层表征提取
# ============================================================

REPRESENTATION_EXTRACTION_PROMPT = """你是一个金融事件分析专家。你的任务是提取一个新闻事件的多层表征，用于后续的历史类比检索。

## 事件信息
标题：{title}
描述：{description}
分类：{category}
相关文章摘要：
{article_summaries}

## 输出要求

请提取事件的三层表征，输出严格的 JSON 格式：

```json
{{
    "surface": {{
        "summary": "事件表面概述（50字以内）",
        "entities": ["美联储", "500基点", "2024-01-15"],
        "numbers": {{"rate_hike_bps": 500, "inflation_rate": 8.5}}
    }},
    
    "structural": {{
        "causal_pattern": "causal_pattern_id",
        "causal_pattern_desc": "因果模式描述（这个事件的因果传导链是什么）",
        "decision_logic": "决策者面临的选择结构（为什么做出这个决策）",
        "transmission_mechanism": "传导机制（这个决策如何影响经济/市场）",
        "constraint_conditions": ["约束条件1", "约束条件2"]
    }},
    
    "abstract": {{
        "economic_principle": "economic_principle_id",
        "economic_principle_desc": "经济学原理描述（这个事件体现了什么经济学原理）",
        "game_theory_structure": "博弈结构描述（各方的策略空间和均衡）",
        "institutional_context": "制度背景（决策发生的制度环境）"
    }}
}}
```

## 因果模式 ID 参考
- tightening_cycle_inflation_response: 紧缩周期-通胀应对
- easing_cycle_recession_response: 宽松周期-衰退应对
- currency_defense_rate_hike: 货币保卫-加息
- supply_shock_price_surge: 供给冲击-价格飙升
- demand_collapse_policy_stimulus: 需求崩塌-政策刺激
- geopolitical_supply_disruption: 地缘政治-供给中断
- tech_disruption_industry_reshape: 技术颠覆-行业重塑
- financial_contagion_crisis_spread: 金融传染-危机蔓延
- regulatory_crackdown_industry_adjust: 监管收紧-行业调整
- bust_cycle_deleveraging: 泡沫破裂-去杠杆
- 如果以上都不匹配，可以创建新的 pattern id

## 经济学原理 ID 参考
- impossible_trinity_tradeoff: 不可能三角权衡
- taylor_rule_deviation: 泰勒规则偏离
- phillips_curve_tradeoff: 菲利普斯曲线权衡
- moral_hazard_distortion: 道德风险扭曲
- adverse_selection_failure: 逆向选择失败
- coordination_failure: 协调失败
- bubble_dynamics: 泡沫动态
- balance_sheet_recession: 资产负债表衰退
- liquidity_trap: 流动性陷阱
- currency_crisis_model: 货币危机模型
- 如果以上都不匹配，可以创建新的 principle id

## 注意事项
1. 因果模式和经济学原理要用英文 ID，方便后续匹配
2. 描述要用中文
3. entities 要提取关键的参与者和数值
4. 要关注结构性特征，不是表面细节"""


# ============================================================
# AI 提示词：历史类比分析
# ============================================================

ANALOGY_ANALYSIS_PROMPT = """你是一个金融历史分析专家。你的任务是分析两个事件之间的结构性类比关系。

## 当前事件
标题：{source_title}
因果模式：{source_causal_pattern}
决策逻辑：{source_decision_logic}
传导机制：{source_transmission}
经济学原理：{source_principle}

## 历史事件
标题：{target_title}
因果模式：{target_causal_pattern}
决策逻辑：{target_decision_logic}
传导机制：{target_transmission}
经济学原理：{target_principle}

## 输出要求

请分析这两个事件的类比关系，输出严格的 JSON 格式：

```json
{{
    "causal_similarity": 0.85,
    "decision_similarity": 0.80,
    "constraint_similarity": 0.70,
    "mechanism_similarity": 0.75,
    "game_similarity": 0.65,
    "overall_similarity": 0.78,
    
    "analogy_type": "structural",
    "analogy_summary": "两个事件的核心类比点（100字以内）",
    "key_insight": "从这个类比中可以获得的关键洞察",
    "lessons_learned": "历史事件的教训，对当前事件的启示",
    
    "surface_differences": [
        "表面差异1：具体实体不同",
        "表面差异2：数值规模不同"
    ],
    "structural_differences": [
        "结构差异1：约束条件略有不同",
        "结构差异2：市场成熟度不同"
    ]
}}
```

## 评分标准
- 1.0: 完全相同
- 0.8: 高度相似
- 0.6: 有明显相似性
- 0.4: 部分相似
- 0.2: 弱相关
- 0.0: 完全不同

## analogy_type 类型
- structural: 结构性类比（因果链同构）
- pattern: 模式类比（决策模式相似）
- principle: 原理类比（经济学原理相同）

## 注意事项
1. 评分要客观，不要因为表面相似就给高分
2. 关注结构层和抽象层的相似性
3. 差异分析同样重要，要指出类比的局限性
4. lessons_learned 要有实际指导意义"""


def build_representation_prompt(title: str, description: str, category: str, articles: list) -> str:
    """构建表征提取提示词"""
    article_summaries = []
    for i, article in enumerate(articles[:5], 1):
        summary = article.get('summary', article.get('title', ''))
        article_summaries.append(f"{i}. {article.get('title', '')} - {summary[:200]}")
    
    return REPRESENTATION_EXTRACTION_PROMPT.format(
        title=title,
        description=description or "无",
        category=category,
        article_summaries="\n".join(article_summaries) if article_summaries else "无相关文章"
    )


def build_analogy_prompt(source: dict, target: dict) -> str:
    """构建类比分析提示词"""
    return ANALOGY_ANALYSIS_PROMPT.format(
        source_title=source.get('title', ''),
        source_causal_pattern=source.get('causal_pattern_desc', ''),
        source_decision_logic=source.get('decision_logic', ''),
        source_transmission=source.get('transmission_mechanism', ''),
        source_principle=source.get('economic_principle_desc', ''),
        target_title=target.get('title', ''),
        target_causal_pattern=target.get('causal_pattern_desc', ''),
        target_decision_logic=target.get('decision_logic', ''),
        target_transmission=target.get('transmission_mechanism', ''),
        target_principle=target.get('economic_principle_desc', ''),
    )


def parse_ai_response(response: str) -> Optional[dict]:
    """解析AI返回的JSON"""
    try:
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


async def extract_event_representation(event: dict, articles: list, ai_client) -> Optional[dict]:
    """
    提取事件的多层表征
    
    Args:
        event: 事件信息
        articles: 相关文章
        ai_client: AI客户端
    
    Returns:
        多层表征字典
    """
    if not ai_client or not ai_client.enabled:
        logger.warning("AI 未启用，跳过表征提取")
        return None
    
    prompt = build_representation_prompt(
        title=event.get('title', ''),
        description=event.get('description', ''),
        category=event.get('category', ''),
        articles=articles
    )
    
    try:
        response = ai_client._call_api(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000
        )
        
        if not response:
            return None
        
        result = parse_ai_response(response)
        if result:
            result['ai_model'] = 'deepseek-chat'
            result['ai_confidence'] = 0.8
        
        return result
        
    except Exception as e:
        logger.error(f"表征提取失败: {e}")
        return None


async def analyze_analogy(source_repr: dict, target_repr: dict, ai_client) -> Optional[dict]:
    """
    分析两个事件之间的类比关系
    
    Args:
        source_repr: 当前事件的表征
        target_repr: 历史事件的表征
        ai_client: AI客户端
    
    Returns:
        类比分析结果
    """
    if not ai_client or not ai_client.enabled:
        return None
    
    prompt = build_analogy_prompt(source_repr, target_repr)
    
    try:
        response = ai_client._call_api(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        
        if not response:
            return None
        
        result = parse_ai_response(response)
        if result:
            result['ai_model'] = 'deepseek-chat'
        
        return result
        
    except Exception as e:
        logger.error(f"类比分析失败: {e}")
        return None


def compute_structural_similarity(source_repr: dict, target_repr: dict) -> Dict[str, float]:
    """
    计算结构相似度（基于规则的快速匹配）
    
    用于预筛选，减少需要调用AI的候选数量
    """
    scores = {}
    
    # 因果模式匹配
    source_causal = source_repr.get('structural', {}).get('causal_pattern', '')
    target_causal = target_repr.get('structural', {}).get('causal_pattern', '')
    scores['causal'] = 1.0 if source_causal == target_causal else 0.0
    
    # 经济学原理匹配
    source_principle = source_repr.get('abstract', {}).get('economic_principle', '')
    target_principle = target_repr.get('abstract', {}).get('economic_principle', '')
    scores['principle'] = 1.0 if source_principle == target_principle else 0.0
    
    # 约束条件重叠度
    source_constraints = set(source_repr.get('structural', {}).get('constraint_conditions', []))
    target_constraints = set(target_repr.get('structural', {}).get('constraint_conditions', []))
    if source_constraints and target_constraints:
        overlap = len(source_constraints & target_constraints)
        total = len(source_constraints | target_constraints)
        scores['constraint'] = overlap / total if total > 0 else 0.0
    else:
        scores['constraint'] = 0.0
    
    # 综合分数
    scores['overall'] = (
        scores['causal'] * 0.4 +
        scores['principle'] * 0.3 +
        scores['constraint'] * 0.3
    )
    
    return scores


def get_analogy_type_label(analogy_type: str, lang: str = 'zh') -> str:
    """获取类比类型标签"""
    labels = {
        'zh': {
            'structural': '结构性类比',
            'pattern': '模式类比',
            'principle': '原理类比',
        },
        'en': {
            'structural': 'Structural Analogy',
            'pattern': 'Pattern Analogy',
            'principle': 'Principle Analogy',
        }
    }
    return labels.get(lang, labels['zh']).get(analogy_type, analogy_type)


def get_dimension_label(dimension: str, lang: str = 'zh') -> str:
    """获取匹配维度标签"""
    from models.event_representation import MATCH_DIMENSIONS
    dim_info = MATCH_DIMENSIONS.get(dimension, {})
    return dim_info.get(f'label_{lang}' if lang == 'en' else 'label', dimension)
