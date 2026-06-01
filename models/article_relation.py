from sqlalchemy import Column, BigInteger, String, Float, DateTime, ForeignKey, Index, func, UniqueConstraint
from models.base import Base


class ArticleRelation(Base):
    __tablename__ = "article_relations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_id = Column(BigInteger, ForeignKey("news.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(BigInteger, ForeignKey("news.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(50), nullable=False, default="keyword_match")
    score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="uq_article_relation"),
        Index("idx_relation_source", "source_id"),
        Index("idx_relation_target", "target_id"),
        Index("idx_relation_type", "relation_type"),
        Index("idx_relation_score", "score"),
    )
