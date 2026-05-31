from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class RunMetrics(Base):
    __tablename__ = "run_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_type = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    sources_attempted = Column(Integer, default=0)
    sources_succeeded = Column(Integer, default=0)
    sources_failed = Column(Integer, default=0)
    items_fetched = Column(Integer, default=0)
    items_deduped = Column(Integer, default=0)
    items_final = Column(Integer, default=0)
    translate_cached = Column(Integer, default=0)
    translate_new = Column(Integer, default=0)
    translate_failed = Column(Integer, default=0)
    details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_metrics_type", "run_type", "started_at"),
    )
