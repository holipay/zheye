from sqlalchemy import Column, BigInteger, String, Date, Text, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False)
    overview = Column(Text)
    hot_topics = Column(JSONB)
    market_sentiment = Column(String(50))
    key_events = Column(JSONB)
    trend_analysis = Column(Text)
    news_count = Column(Integer, default=0)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
