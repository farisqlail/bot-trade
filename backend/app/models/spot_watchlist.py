from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func, Text
from sqlalchemy.orm import relationship
from app.database import Base


class SpotWatchlist(Base):
    __tablename__ = "spot_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    symbol = Column(String(20), nullable=False, index=True)
    contract_address = Column(String(100), nullable=True)
    network = Column(String(50), nullable=False, default="arbitrum")

    target_buy_price = Column(Float, nullable=True)
    target_sell_price = Column(Float, nullable=True)
    alert_enabled = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
