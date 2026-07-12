from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func

from models.base import Base


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("tracked_companies.id"), nullable=False)
    news_id = Column(BigInteger, ForeignKey("news.id"), nullable=False)
    dimension = Column(String(50), nullable=False)
    direction = Column(String(20), nullable=False)
    strength = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    source = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("news_id", "company_id", "dimension", "source", name="uq_evidence_record"),
        Index("idx_evidence_company", "company_id", "created_at"),
    )
