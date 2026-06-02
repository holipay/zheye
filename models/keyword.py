from sqlalchemy import Column, BigInteger, String, Float, DateTime, Index, func, UniqueConstraint
from models.base import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    term = Column(String(200), nullable=False)
    lang = Column(String(10), nullable=False, default="en")
    category = Column(String(50), nullable=False)
    weight = Column(Float, default=1.0)
    group_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("term", "lang", name="uq_keyword_term_lang"),
        Index("idx_keyword_category", "category"),
        Index("idx_keyword_lang", "lang"),
        Index("idx_keyword_group_id", "group_id"),
    )
