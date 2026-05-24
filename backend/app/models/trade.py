from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, func, Text
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class TradeDirection(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    LIQUIDATED = "LIQUIDATED"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    exchange_order_id = Column(String(100), nullable=True, index=True)
    symbol = Column(String(255), nullable=False, index=True)
    direction = Column(Enum(TradeDirection, native_enum=False), nullable=False)
    status = Column(Enum(TradeStatus, native_enum=False), default=TradeStatus.PENDING, index=True)

    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)

    quantity = Column(Float, nullable=False)
    leverage = Column(Integer, default=10)
    risk_amount = Column(Float, nullable=False)
    risk_percent = Column(Float, nullable=False)

    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    fees = Column(Float, default=0.0)

    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)
    notes = Column(Text, nullable=True)

    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="trades")
    signal = relationship("Signal", back_populates="trades")
