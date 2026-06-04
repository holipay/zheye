"""
深度分析模块
提供知识框架、因果链、历史类比、情景推演等高级分析功能

此模块为可选组件，通过 settings.ENABLE_DEEP_ANALYST 启用
"""

from deep_analyst.knowledge import analyze_event_knowledge, analyze_causal_chain
from deep_analyst.analogy import extract_event_representation, analyze_analogy, compute_structural_similarity
from deep_analyst.scenario import analyze_scenarios
from deep_analyst.ai_analysis import DeepSeekClient

__all__ = [
    "analyze_event_knowledge",
    "analyze_causal_chain",
    "extract_event_representation",
    "analyze_analogy",
    "compute_structural_similarity",
    "analyze_scenarios",
    "DeepSeekClient",
]
