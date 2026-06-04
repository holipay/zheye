"""
因果链模型
多层次因果分析：根源 → 触发 → 即时影响 → 短期效应 → 长期走向
"""

from sqlalchemy import Column, BigInteger, String, Text, Float, DateTime, Index, func, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class CausalNode(Base):
    """因果节点"""
    __tablename__ = "causal_nodes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False)
    
    # 节点信息
    node_type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # 因果属性
    probability = Column(Float)  # 用于 future_scenarios
    impact_level = Column(String(20))  # high/medium/low
    time_horizon = Column(String(50))  # immediate/days/weeks/months/years
    
    # 关联
    evidence = Column(JSONB)  # 文章ID列表
    entities = Column(JSONB)  # 涉及实体
    confidence = Column(Float, default=0.8)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_causal_nodes_event", "event_id"),
        Index("idx_causal_nodes_type", "node_type"),
    )


class CausalLink(Base):
    """因果关系"""
    __tablename__ = "causal_links"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 关系（添加外键约束）
    source_node_id = Column(BigInteger, ForeignKey("causal_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(BigInteger, ForeignKey("causal_nodes.id", ondelete="CASCADE"), nullable=False)
    
    # 关系属性
    link_type = Column(String(50), default='causes')  # causes/enables/leads_to/triggers
    strength = Column(Float, default=1.0)  # 关系强度 0-1
    description = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", name="uq_causal_link"),
        Index("idx_causal_links_source", "source_node_id"),
        Index("idx_causal_links_target", "target_node_id"),
    )


# 节点类型常量
class NodeType:
    ROOT_CAUSE = "root_cause"      # 根本原因
    TRIGGER = "trigger"            # 触发因素
    IMMEDIATE = "immediate"        # 即时影响
    SHORT_TERM = "short_term"      # 短期效应
    LONG_TERM = "long_term"        # 长期走向
    SCENARIO = "scenario"          # 可能情景

    @classmethod
    def get_label(cls, node_type: str, lang: str = 'zh') -> str:
        labels = {
            'zh': {
                cls.ROOT_CAUSE: '根本原因',
                cls.TRIGGER: '触发因素',
                cls.IMMEDIATE: '即时影响',
                cls.SHORT_TERM: '短期效应',
                cls.LONG_TERM: '长期走向',
                cls.SCENARIO: '可能情景',
            },
            'en': {
                cls.ROOT_CAUSE: 'Root Cause',
                cls.TRIGGER: 'Trigger',
                cls.IMMEDIATE: 'Immediate Impact',
                cls.SHORT_TERM: 'Short-term Effect',
                cls.LONG_TERM: 'Long-term Outlook',
                cls.SCENARIO: 'Scenario',
            }
        }
        return labels.get(lang, labels['zh']).get(node_type, node_type)

    @classmethod
    def get_icon(cls, node_type: str) -> str:
        icons = {
            cls.ROOT_CAUSE: '🌱',
            cls.TRIGGER: '⚡',
            cls.IMMEDIATE: '💥',
            cls.SHORT_TERM: '📈',
            cls.LONG_TERM: '🔮',
            cls.SCENARIO: '🎯',
        }
        return icons.get(node_type, '•')
