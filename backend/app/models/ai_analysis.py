from sqlalchemy import Column, Integer, String, Float, DateTime, func, Text, JSON
from app.database import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(255), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)

    trend = Column(String(20), nullable=True)
    sentiment = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=True)

    support_levels = Column(JSON, nullable=True)
    resistance_levels = Column(JSON, nullable=True)
    key_levels = Column(JSON, nullable=True)

    analysis_text = Column(Text, nullable=False)
    raw_response = Column(Text, nullable=True)
    market_data_snapshot = Column(JSON, nullable=True)

    price_at_analysis = Column(Float, nullable=True)
    recommended_action = Column(String(20), nullable=True)
    suggested_entry = Column(Float, nullable=True)
    suggested_sl = Column(Float, nullable=True)
    suggested_tp = Column(Float, nullable=True)

    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
