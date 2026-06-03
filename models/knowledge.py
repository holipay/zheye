from sqlalchemy import Column, BigInteger, String, Text, Float, Boolean, Integer, DateTime, Index, func, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class KnowledgeAtom(Base):
    """知识原子：可复用的知识单元"""
    __tablename__ = "knowledge_atoms"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    atom_type = Column(String(50), nullable=False)  # background/context/history/definition/mechanism
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50))
    entities = Column(JSONB)  # ["美联储", "通胀"]
    keywords = Column(JSONB)  # ["加息", "货币政策"]
    source_article_id = Column(BigInteger)
    confidence = Column(Float, default=0.8)
    lang = Column(String(10), default='zh')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_knowledge_atoms_type", "atom_type"),
        Index("idx_knowledge_atoms_category", "category"),
        Index("idx_knowledge_atoms_lang", "lang"),
    )


class EventKnowledge(Base):
    """事件知识：事件的知识框架"""
    __tablename__ = "event_knowledge"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), unique=True, nullable=False)
    
    # 知识框架
    background_summary = Column(Text)  # 背景概述
    knowledge_gaps = Column(JSONB)  # 知识缺口列表
    causal_chain = Column(JSONB)  # 因果链
    key_concepts = Column(JSONB)  # 关键概念列表
    
    # 元数据
    ai_model = Column(String(50))
    ai_confidence = Column(Float)
    analysis_version = Column(Integer, default=1)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EventKnowledgeAtom(Base):
    """事件-知识原子关联"""
    __tablename__ = "event_knowledge_atoms"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), ForeignKey("event_knowledge.event_id", ondelete="CASCADE"), nullable=False)
    atom_id = Column(BigInteger, ForeignKey("knowledge_atoms.id", ondelete="CASCADE"), nullable=False)
    relevance = Column(Float, default=1.0)
    position = Column(Integer)  # 排序位置
    is_required = Column(Boolean, default=True)  # 是否必要知识
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("event_id", "atom_id", name="uq_event_atom"),
        Index("idx_event_atoms_event", "event_id"),
        Index("idx_event_atoms_atom", "atom_id"),
    )
