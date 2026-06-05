from sqlalchemy import Column, BigInteger, String, DateTime, func
from models.base import Base


class TranslationCache(Base):
    __tablename__ = "translation_cache"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_text = Column(String(1000), nullable=False)
    translated_text = Column(String(1000), nullable=False)
    source_hash = Column(String(64), nullable=False, unique=True)
    provider = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
