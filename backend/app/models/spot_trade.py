from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, func, Text
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class SpotTradeType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class SpotTradeStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SpotTrade(Base):
    __tablename__ = "spot_trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    symbol = Column(String(50), nullable=False, index=True)
    base_token = Column(String(20), nullable=False)
    quote_token = Column(String(20), nullable=False)

    trade_type = Column(Enum(SpotTradeType, native_enum=False), nullable=False)
    status = Column(Enum(SpotTradeStatus, native_enum=False), default=SpotTradeStatus.PENDING, index=True)

    amount_in = Column(Float, nullable=False)
    amount_out = Column(Float, nullable=True)
    price_at_trade = Column(Float, nullable=True)
    price_target = Column(Float, nullable=True)

    tx_hash = Column(String(100), nullable=True, index=True)
    network = Column(String(50), nullable=False, default="arbitrum")

    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
