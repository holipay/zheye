from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class TrackedCompany(Base):
    __tablename__ = "tracked_companies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_id = Column(BigInteger, ForeignKey("entities.id"), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    config = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
