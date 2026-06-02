from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    data_type = Column(String(20), nullable=False)  # forex, commodity, stock, crypto
    symbol = Column(String(20), nullable=False)
    value = Column(Numeric(20, 6), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    extra_data = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_market_data_symbol", "symbol", "timestamp"),
        Index("idx_market_data_type", "data_type", "timestamp"),
    )
