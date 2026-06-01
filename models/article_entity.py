from sqlalchemy import Column, BigInteger, String, Float, DateTime, ForeignKey, Index, func, UniqueConstraint
from models.base import Base


class ArticleEntity(Base):
    __tablename__ = "article_entities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, ForeignKey("news.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    context = Column(String(500))
    relevance = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("article_id", "entity_id", name="uq_article_entity"),
        Index("idx_article_entity_article", "article_id"),
        Index("idx_article_entity_entity", "entity_id"),
    )
