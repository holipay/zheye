from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Float, Index, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from models.base import Base


class News(Base):
    __tablename__ = "news"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    translated_title = Column(String(500))
    link = Column(String(1000), nullable=False)
    link_hash = Column(String(64), nullable=False, unique=True)
    source = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    lang = Column(String(10), nullable=False, default="en")
    summary = Column(Text)
    content = Column(Text)
    article_type = Column(String(20), default="news")
    regions = Column(JSONB)
    date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # AI 分析字段
    ai_sentiment = Column(String(20))  # positive, negative, neutral
    ai_sentiment_score = Column(Float)  # -1.0 到 1.0
    ai_summary_zh = Column(Text)  # AI 生成的中文摘要
    ai_key_points = Column(JSONB)  # 关键要点列表
    ai_tags = Column(JSONB)  # AI 生成的标签
    ai_importance = Column(Float, default=0.0)  # 重要性评分 0-1
    ai_analyzed_at = Column(DateTime(timezone=True))  # 分析时间

    # 全文搜索列（由触发器自动维护）
    search_vector = Column(TSVECTOR)

    __table_args__ = (
        Index("idx_news_category_date", "category", "date"),
        Index("idx_news_source", "source"),
        Index("idx_news_created", "created_at"),
        Index("idx_news_sentiment", "ai_sentiment"),
        Index("idx_news_importance", "ai_importance"),
        Index("idx_news_regions", "regions", postgresql_using="gin"),
        Index("idx_news_search_vector", "search_vector", postgresql_using="gin"),
    )
