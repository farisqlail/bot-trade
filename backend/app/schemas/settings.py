from pydantic import BaseModel
from typing import Optional, Dict, Any


class SettingsUpdate(BaseModel):
    symbol: Optional[str] = None
    leverage: Optional[int] = None
    risk_percent: Optional[float] = None
    max_open_trades: Optional[int] = None
    default_stop_loss: Optional[float] = None
    default_take_profit: Optional[float] = None
    daily_loss_limit_percent: Optional[float] = None
    max_drawdown_percent: Optional[float] = None
    consecutive_loss_limit: Optional[int] = None
    bot_enabled: Optional[bool] = None
    auto_trade: Optional[bool] = None
    ai_analysis_enabled: Optional[bool] = None
    ai_analysis_interval: Optional[int] = None
    polymarket_api_key: Optional[str] = None
    polymarket_api_secret: Optional[str] = None
    polymarket_api_passphrase: Optional[str] = None
    use_public_data_only: Optional[bool] = None
    scanner_watchlist: Optional[str] = None
    paper_balance: Optional[float] = None
    notification_settings: Optional[Dict[str, Any]] = None


class SettingsResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    leverage: int
    risk_percent: float
    max_open_trades: int
    default_stop_loss: float
    default_take_profit: float
    daily_loss_limit_percent: float
    max_drawdown_percent: float
    consecutive_loss_limit: int
    bot_enabled: bool
    auto_trade: bool
    ai_analysis_enabled: bool
    ai_analysis_interval: int
    use_public_data_only: bool
    polymarket_api_key: Optional[str] = None
    polymarket_api_passphrase: Optional[str] = None
    scanner_watchlist: list[str]
    paper_balance: float

    model_config = {"from_attributes": True}
