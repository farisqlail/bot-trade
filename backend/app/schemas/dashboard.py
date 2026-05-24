from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AccountMetrics(BaseModel):
    balance: float
    equity: float
    unrealized_pnl: float
    margin_used: float
    free_margin: float


class PnLMetrics(BaseModel):
    daily_pnl: float
    daily_pnl_percent: float
    weekly_pnl: float
    weekly_pnl_percent: float
    monthly_pnl: float
    monthly_pnl_percent: float
    total_pnl: float


class TradeMetrics(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    best_trade: float
    worst_trade: float


class RiskStatus(BaseModel):
    status: str  # SAFE, WARNING, DANGER, CRITICAL
    daily_loss_percent: float
    daily_loss_limit_percent: float
    current_drawdown_percent: float
    max_drawdown_percent: float
    open_positions: int
    max_open_trades: int
    consecutive_losses: int
    consecutive_loss_limit: int


class BotStatus(BaseModel):
    is_running: bool
    auto_trade: bool
    ai_enabled: bool
    symbol: str
    last_signal_at: Optional[datetime] = None
    last_trade_at: Optional[datetime] = None
    uptime_seconds: Optional[int] = None


class DashboardResponse(BaseModel):
    account: AccountMetrics
    pnl: PnLMetrics
    trades: TradeMetrics
    risk: RiskStatus
    bot: BotStatus
    last_updated: datetime
