import secrets
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey, JSON, func
from app.database import Base


class TuningHistory(Base):
    __tablename__ = "tuning_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(String(20), default="pending", index=True)
    # pending | approved | rejected | auto_applied | skipped

    old_risk_percent = Column(Float, nullable=False)
    new_risk_percent = Column(Float, nullable=False)
    change_direction = Column(String(10))  # increase | decrease | no_change

    reason = Column(Text)
    metrics_snapshot = Column(JSON)
    # {win_rate, profit_factor, total_trades, max_consecutive_losses, avg_pnl, period_days}

    telegram_message_id = Column(Integer, nullable=True)
    approval_token = Column(String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
