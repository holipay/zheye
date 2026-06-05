from sqlalchemy import Column, BigInteger, Float, DateTime, ForeignKey, Index, func, UniqueConstraint
from models.base import Base


class ArticleKeyword(Base):
    __tablename__ = "article_keywords"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, ForeignKey("news.id", ondelete="CASCADE"), nullable=False)
    keyword_id = Column(BigInteger, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    relevance = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("article_id", "keyword_id", name="uq_article_keyword"),
        Index("idx_article_keyword_keyword", "keyword_id"),
    )
