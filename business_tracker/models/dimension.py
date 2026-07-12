from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, String, UniqueConstraint, func

from models.base import Base


class CompanyDimension(Base):
    __tablename__ = "company_dimensions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("tracked_companies.id"), nullable=False)
    dimension = Column(String(50), nullable=False)
    alpha = Column(Float, nullable=False)
    beta = Column(Float, nullable=False)
    mean = Column(Float, nullable=False)
    variance = Column(Float, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(50), default="system")

    __table_args__ = (
        UniqueConstraint("company_id", "dimension", name="uq_company_dimension"),
    )
