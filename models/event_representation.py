"""
事件多层表征模型
用于历史类比检索的结构化匹配
"""

from sqlalchemy import Column, BigInteger, String, Text, Float, DateTime, Index, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class EventRepresentation(Base):
    """事件多层表征"""
    __tablename__ = "event_representations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), unique=True, nullable=False)
    
    # 表面层
    surface_summary = Column(Text)
    surface_entities = Column(JSONB)  # ["美联储", "500基点"]
    surface_numbers = Column(JSONB)  # {"rate_hike_bps": 500}
    
    # 结构层
    causal_pattern = Column(String(200))  # 因果模式标签
    causal_pattern_desc = Column(Text)
    decision_logic = Column(Text)  # 决策逻辑
    transmission_mechanism = Column(Text)  # 传导机制
    constraint_conditions = Column(JSONB)  # 约束条件
    
    # 抽象层
    economic_principle = Column(String(200))  # 经济学原理标签
    economic_principle_desc = Column(Text)
    game_theory_structure = Column(Text)
    institutional_context = Column(Text)
    
    # 匹配用向量
    pattern_embedding = Column(JSONB)
    
    # 元数据
    ai_model = Column(String(50))
    ai_confidence = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_event_repr_event", "event_id"),
        Index("idx_event_repr_causal", "causal_pattern"),
        Index("idx_event_repr_economic", "economic_principle"),
    )


class HistoricalAnalogy(Base):
    """历史类比"""
    __tablename__ = "historical_analogies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_event_id = Column(String(100), nullable=False)  # 当前事件
    target_event_id = Column(String(100), nullable=False)  # 历史事件
    
    # 匹配维度评分
    causal_similarity = Column(Float)  # 因果模式相似度
    decision_similarity = Column(Float)  # 决策逻辑相似度
    constraint_similarity = Column(Float)  # 约束条件相似度
    mechanism_similarity = Column(Float)  # 传导机制相似度
    game_similarity = Column(Float)  # 博弈结构相似度
    overall_similarity = Column(Float)  # 综合相似度
    
    # 类比描述
    analogy_type = Column(String(50))  # structural/pattern/principle
    analogy_summary = Column(Text)
    key_insight = Column(Text)  # 关键洞察
    lessons_learned = Column(Text)  # 历史教训
    
    # 差异分析
    surface_differences = Column(JSONB)
    structural_differences = Column(JSONB)
    
    # 元数据
    confidence = Column(Float)
    ai_model = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source_event_id", "target_event_id", name="uq_analogy"),
        Index("idx_analogies_source", "source_event_id"),
        Index("idx_analogies_target", "target_event_id"),
        Index("idx_analogies_similarity", "overall_similarity"),
    )


# 匹配维度权重
MATCH_DIMENSIONS = {
    "causal": {"weight": 0.30, "label": "因果模式", "label_en": "Causal Pattern"},
    "decision": {"weight": 0.25, "label": "决策逻辑", "label_en": "Decision Logic"},
    "constraint": {"weight": 0.15, "label": "约束条件", "label_en": "Constraints"},
    "mechanism": {"weight": 0.20, "label": "传导机制", "label_en": "Transmission"},
    "game": {"weight": 0.10, "label": "博弈结构", "label_en": "Game Structure"},
}

# 因果模式分类
CAUSAL_PATTERNS = {
    "tightening_cycle_inflation_response": "紧缩周期-通胀应对",
    "easing_cycle_recession_response": "宽松周期-衰退应对",
    "currency_defense_rate_hike": "货币保卫-加息",
    "supply_shock_price_surge": "供给冲击-价格飙升",
    "demand_collapse_policy_stimulus": "需求崩塌-政策刺激",
    "geopolitical_supply_disruption": "地缘政治-供给中断",
    "tech_disruption_industry_reshape": "技术颠覆-行业重塑",
    "financial_contagion_crisis_spread": "金融传染-危机蔓延",
    "regulatory_crackdown_industry_adjust": "监管收紧-行业调整",
    "bust_cycle_deleveraging": "泡沫破裂-去杠杆",
}

# 经济学原理分类
ECONOMIC_PRINCIPLES = {
    "impossible_trinity_tradeoff": "不可能三角权衡",
    "taylor_rule_deviation": "泰勒规则偏离",
    "phillips_curve_tradeoff": "菲利普斯曲线权衡",
    "moral_hazard_distortion": "道德风险扭曲",
    "adverse_selection_failure": "逆向选择失败",
    "coordination_failure": "协调失败",
    "bubble_dynamics": "泡沫动态",
    "balance_sheet_recession": "资产负债表衰退",
    "liquidity_trap": "流动性陷阱",
    "currency_crisis_model": "货币危机模型",
}
