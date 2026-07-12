from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Index, String, func

from models.base import Base


class BeliefHistory(Base):
    __tablename__ = "belief_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("tracked_companies.id"), nullable=False)
    dimension = Column(String(50), nullable=False)
    alpha = Column(Float, nullable=False)
    beta = Column(Float, nullable=False)
    mean = Column(Float, nullable=False)
    variance = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_belief_history_company_dim", "company_id", "dimension", "recorded_at"),
    )
