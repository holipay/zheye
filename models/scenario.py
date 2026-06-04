"""
事件情景推演模型
提供思考框架，而非预测结论
"""

from sqlalchemy import Column, BigInteger, String, Text, Float, DateTime, Index, func, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class EventScenario(Base):
    """事件情景推演"""
    __tablename__ = "event_scenarios"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), ForeignKey("events.event_id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # 核心框架
    key_variables = Column(JSONB)  # 关键变量列表
    observation_signals = Column(JSONB)  # 观察信号清单
    scenarios = Column(JSONB)  # 情景框架
    thinking_questions = Column(JSONB)  # 思考问题
    
    # 元数据
    ai_model = Column(String(50))
    ai_confidence = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_event_scenarios_event", "event_id"),
    )
