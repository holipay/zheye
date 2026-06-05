from sqlalchemy import Column, BigInteger, String, Date, Text, Integer, DateTime, Index, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class Trend(Base):
    __tablename__ = "trends"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    keyword = Column(String(100), nullable=False)
    count = Column(Integer, default=0)
    sentiment = Column(String(20))
    trend = Column(String(20))  # rising, stable, declining
    analysis = Column(Text)
    related_topics = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("date", "keyword", name="uq_trends_date_keyword"),
        Index("idx_trends_keyword", "keyword"),
    )
