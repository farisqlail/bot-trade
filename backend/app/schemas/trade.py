from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
from app.models.trade import TradeDirection, TradeStatus


class TradeCreate(BaseModel):
    symbol: str = "featured"
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_percent: float = 1.0
    leverage: int = 10
    signal_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("risk_percent")
    @classmethod
    def validate_risk(cls, v):
        if v <= 0 or v > 10:
            raise ValueError("Risk percent must be between 0.01 and 10")
        return v

    @field_validator("leverage")
    @classmethod
    def validate_leverage(cls, v):
        if v < 1 or v > 125:
            raise ValueError("Leverage must be between 1 and 125")
        return v


class TradeResponse(BaseModel):
    id: int
    user_id: int
    exchange_order_id: Optional[str] = None
    symbol: str
    direction: TradeDirection
    status: TradeStatus
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_price: Optional[float] = None
    quantity: float
    leverage: int
    risk_amount: float
    risk_percent: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    fees: float
    notes: Optional[str] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TradeUpdate(BaseModel):
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None


class TradeClose(BaseModel):
    exit_price: float
    notes: Optional[str] = None
