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
    scan_all_coins: Optional[bool] = None
    max_scan_coins: Optional[int] = None
    min_volume_filter: Optional[float] = None
    auto_tuning_enabled: Optional[bool] = None
    tuning_frequency: Optional[str] = None
    require_manual_approval_for_tuning: Optional[bool] = None
    notification_settings: Optional[Dict[str, Any]] = None
    defi_enabled: Optional[bool] = None
    defi_network: Optional[str] = None
    defi_wallet_address: Optional[str] = None
    defi_private_key: Optional[str] = None
    defi_trade_percent: Optional[float] = None
    defi_slippage: Optional[float] = None


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
    scan_all_coins: bool = False
    max_scan_coins: int = 50
    min_volume_filter: float = 5_000_000.0
    auto_tuning_enabled: bool = False
    tuning_frequency: str = "weekly"
    require_manual_approval_for_tuning: bool = True
    defi_enabled: bool = False
    defi_network: str = "arbitrum"
    defi_wallet_address: Optional[str] = None
    defi_has_private_key: bool = False
    defi_trade_percent: float = 50.0
    defi_slippage: float = 0.5

    model_config = {"from_attributes": True}
