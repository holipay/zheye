from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, Numeric, Index, func
from models.base import Base


class SourceHealth(Base):
    __tablename__ = "source_health"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False, unique=True)
    total_checks = Column(Integer, default=0)
    total_success = Column(Integer, default=0)
    total_failure = Column(Integer, default=0)
    consecutive_failures = Column(Integer, default=0)
    last_check = Column(DateTime(timezone=True))
    last_success = Column(DateTime(timezone=True))
    last_error = Column(Text)
    last_items = Column(Integer, default=0)
    success_rate = Column(Numeric(5, 2), default=0)
    last_etag = Column(String(200))
    last_rss_modified = Column(String(200))
