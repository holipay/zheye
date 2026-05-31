from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Index, func
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
    lang = Column(String(10), default="en")
    summary = Column(Text)
    date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_news_category_date", "category", "date"),
        Index("idx_news_source", "source"),
        Index("idx_news_created", "created_at"),
    )
