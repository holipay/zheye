from datetime import date as date_type
from sqlalchemy import Column, BigInteger, String, Date, Text, Integer, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    analysis = Column(Text, nullable=False)
    structured = Column(JSONB)
    hot_keywords = Column(JSONB)
    perspective = Column(String(50))
    news_count = Column(Integer, default=0)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_analyses_keywords", "hot_keywords", postgresql_using="gin"),
    )
