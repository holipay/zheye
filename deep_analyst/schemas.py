"""
深度分析 Schema
复用 models.schemas 中的基础定义，添加深度分析特有的 Schema。
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

# 复用基础 Schema
from models.schemas import (
    SentimentType,
    Priority,
    TrendType,
    KeyPoint,
    HotTopic,
    KeyEvent,
    ArticleAnalysisSchema,
    DailyReportSchema,
    TrendSchema,
    SCHEMA_MAP as BASE_SCHEMA_MAP,
    get_schema as base_get_schema,
)


# ============================================================
# 深度分析特有枚举
# ============================================================

class NodeType(str, Enum):
    """因果节点类型"""
    cause = "cause"
    effect = "effect"
    trigger = "trigger"
    condition = "condition"


class LinkType(str, Enum):
    """因果关系类型"""
    causes = "causes"
    leads_to = "leads_to"
    triggers = "triggers"
    enables = "enables"
    may_cause = "may_cause"


class AnalogyType(str, Enum):
    """类比类型"""
    structural = "structural"
    pattern = "pattern"
    principle = "principle"


# ============================================================
# 知识框架 Schema
# ============================================================

class KnowledgeGapSchema(BaseModel):
    """知识缺口"""
    topic: str = Field(max_length=200)
    why_needed: str = Field(max_length=500)
    priority: Priority = Field(default=Priority.medium)


class CausalStepSchema(BaseModel):
    """因果步骤"""
    step: int = Field(ge=1)
    cause: str = Field(max_length=500)
    effect: str = Field(max_length=500)
    evidence: Optional[str] = Field(None, max_length=500)


class KeyConceptSchema(BaseModel):
    """关键概念"""
    concept: str = Field(max_length=200)
    definition: str = Field(max_length=500)
    relevance: Optional[str] = Field(None, max_length=500)


class KnowledgeAtomSchema(BaseModel):
    """知识原子"""
    atom_type: str = Field(max_length=50)
    title: str = Field(max_length=200)
    content: str = Field(max_length=2000)
    entities: List[str] = Field(default_factory=list, max_length=20)
    keywords: List[str] = Field(default_factory=list, max_length=20)


class KnowledgeAnalysisSchema(BaseModel):
    """知识分析结果"""
    background_summary: str = Field(default="", max_length=2000)
    knowledge_gaps: List[KnowledgeGapSchema] = Field(default_factory=list, max_length=10)
    causal_chain: List[CausalStepSchema] = Field(default_factory=list, max_length=20)
    key_concepts: List[KeyConceptSchema] = Field(default_factory=list, max_length=15)
    knowledge_atoms: List[KnowledgeAtomSchema] = Field(default_factory=list, max_length=20)


# ============================================================
# 因果链 Schema
# ============================================================

class CausalNodeSchema(BaseModel):
    """因果节点"""
    id: str = Field(max_length=50)
    node_type: NodeType = Field(default=NodeType.cause)
    title: str = Field(max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    impact_level: Optional[str] = Field(None, max_length=50)
    time_horizon: Optional[str] = Field(None, max_length=100)
    entities: List[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class CausalLinkSchema(BaseModel):
    """因果关系"""
    source: str = Field(max_length=50)
    target: str = Field(max_length=50)
    link_type: LinkType = Field(default=LinkType.causes)
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    description: Optional[str] = Field(None, max_length=500)


class CausalChainSchema(BaseModel):
    """因果链分析结果"""
    nodes: List[CausalNodeSchema] = Field(default_factory=list, max_length=50)
    links: List[CausalLinkSchema] = Field(default_factory=list, max_length=100)
    summary: Optional[str] = Field(None, max_length=2000)


# ============================================================
# 事件表征 Schema
# ============================================================

class SurfaceLayerSchema(BaseModel):
    """表面层表征"""
    summary: str = Field(default="", max_length=500)
    entities: List[str] = Field(default_factory=list, max_length=30)
    numbers: Dict[str, Any] = Field(default_factory=dict)


class StructuralLayerSchema(BaseModel):
    """结构层表征"""
    causal_pattern: str = Field(default="", max_length=100)
    causal_pattern_desc: str = Field(default="", max_length=1000)
    decision_logic: str = Field(default="", max_length=1000)
    transmission_mechanism: str = Field(default="", max_length=1000)
    constraint_conditions: List[str] = Field(default_factory=list, max_length=10)


class AbstractLayerSchema(BaseModel):
    """抽象层表征"""
    economic_principle: str = Field(default="", max_length=100)
    economic_principle_desc: str = Field(default="", max_length=1000)
    game_theory_structure: Optional[str] = Field(None, max_length=1000)
    institutional_context: Optional[str] = Field(None, max_length=1000)


class EventRepresentationSchema(BaseModel):
    """事件多层表征"""
    surface: SurfaceLayerSchema = Field(default_factory=SurfaceLayerSchema)
    structural: StructuralLayerSchema = Field(default_factory=StructuralLayerSchema)
    abstract: AbstractLayerSchema = Field(default_factory=AbstractLayerSchema)


# ============================================================
# 历史类比 Schema
# ============================================================

class AnalogyResultSchema(BaseModel):
    """类比分析结果"""
    causal_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    decision_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    constraint_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    mechanism_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    game_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    analogy_type: AnalogyType = Field(default=AnalogyType.structural)
    analogy_summary: str = Field(default="", max_length=1000)
    key_insight: Optional[str] = Field(None, max_length=500)
    lessons_learned: Optional[str] = Field(None, max_length=1000)
    surface_differences: List[str] = Field(default_factory=list, max_length=10)
    structural_differences: List[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


# ============================================================
# 情景推演 Schema
# ============================================================

class KeyVariableSchema(BaseModel):
    """关键变量"""
    name: str = Field(max_length=200)
    why_important: str = Field(max_length=500)
    current_status: Optional[str] = Field(None, max_length=500)
    data_source: Optional[str] = Field(None, max_length=500)


class ObservationSignalSchema(BaseModel):
    """观察信号"""
    signal: str = Field(max_length=200)
    what_to_watch: str = Field(max_length=500)
    frequency: Optional[str] = Field(None, max_length=50)
    source: Optional[str] = Field(None, max_length=200)


class ScenarioSchema(BaseModel):
    """情景"""
    name: str = Field(max_length=200)
    description: str = Field(max_length=1000)
    trigger_conditions: List[str] = Field(default_factory=list, max_length=10)
    observation_cues: List[str] = Field(default_factory=list, max_length=10)
    implications: Optional[str] = Field(None, max_length=1000)


class ThinkingQuestionSchema(BaseModel):
    """思考问题"""
    question: str = Field(max_length=500)
    purpose: Optional[str] = Field(None, max_length=500)
    perspective: Optional[str] = Field(None, max_length=200)


class ScenarioAnalysisSchema(BaseModel):
    """情景推演结果"""
    key_variables: List[KeyVariableSchema] = Field(default_factory=list, max_length=10)
    observation_signals: List[ObservationSignalSchema] = Field(default_factory=list, max_length=20)
    scenarios: List[ScenarioSchema] = Field(default_factory=list, max_length=10)
    thinking_questions: List[ThinkingQuestionSchema] = Field(default_factory=list, max_length=10)
    framework_summary: Optional[str] = Field(None, max_length=1000)


# ============================================================
# Schema 映射表（合并基础和深度分析）
# ============================================================

SCHEMA_MAP = {
    **BASE_SCHEMA_MAP,
    "knowledge": KnowledgeAnalysisSchema,
    "causal_chain": CausalChainSchema,
    "representation": EventRepresentationSchema,
    "analogy": AnalogyResultSchema,
    "scenario": ScenarioAnalysisSchema,
}


def get_schema(name: str) -> Optional[BaseModel]:
    """获取 Schema 类"""
    return SCHEMA_MAP.get(name)
