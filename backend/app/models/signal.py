from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, func, Text, Boolean
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class SignalType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalSource(str, enum.Enum):
    AI = "AI"
    MANUAL = "MANUAL"
    INDICATOR = "INDICATOR"
    WEBHOOK = "WEBHOOK"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(255), nullable=False, index=True)
    signal_type = Column(Enum(SignalType, native_enum=False), nullable=False)
    source = Column(Enum(SignalSource, native_enum=False), default=SignalSource.AI)

    price_at_signal = Column(Float, nullable=False)
    suggested_entry = Column(Float, nullable=True)
    suggested_sl = Column(Float, nullable=True)
    suggested_tp = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)

    reasoning = Column(Text, nullable=True)
    indicators = Column(Text, nullable=True)
    is_executed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    trades = relationship("Trade", back_populates="signal")
