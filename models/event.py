from sqlalchemy import Column, BigInteger, String, Date, Text, Integer, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), unique=True, nullable=False)
    title = Column(String(500))
    description = Column(Text)
    category = Column(String(50))
    first_seen = Column(Date)
    last_updated = Column(Date)
    update_count = Column(Integer, default=1)
    status = Column(String(20), default="active")
    related_articles = Column(JSONB)
    data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_events_status", "status", "last_updated"),
        Index("idx_events_category", "category"),
    )
