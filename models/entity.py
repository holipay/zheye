from sqlalchemy import Column, BigInteger, String, DateTime, Index, func, UniqueConstraint
from models.base import Base


class Entity(Base):
    __tablename__ = "entities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    entity_type = Column(String(50), nullable=False)
    normalized_name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("normalized_name", "entity_type", name="uq_entity_normalized"),
        Index("idx_entity_type", "entity_type"),
    )
