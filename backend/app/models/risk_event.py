from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, func, Text, JSON
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class RiskEventType(str, enum.Enum):
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    POSITION_SIZE_EXCEEDED = "POSITION_SIZE_EXCEEDED"
    LEVERAGE_LIMIT = "LEVERAGE_LIMIT"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    MARGIN_CALL = "MARGIN_CALL"
    BOT_PAUSED = "BOT_PAUSED"
    EMERGENCY_CLOSE = "EMERGENCY_CLOSE"


class RiskSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(Enum(RiskEventType, native_enum=False), nullable=False)
    severity = Column(Enum(RiskSeverity, native_enum=False), nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    triggered_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    action_taken = Column(String(200), nullable=True)
    event_metadata = Column(JSON, nullable=True)

    is_resolved = Column(Integer, default=0)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="risk_events")
