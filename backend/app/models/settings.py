from sqlalchemy import Column, Integer, Float, Boolean, DateTime, ForeignKey, String, func, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    symbol = Column(String(255), default="featured")
    leverage = Column(Integer, default=10)
    risk_percent = Column(Float, default=1.0)
    max_open_trades = Column(Integer, default=5)

    default_stop_loss = Column(Float, default=103500.0)
    default_take_profit = Column(Float, default=107000.0)

    daily_loss_limit_percent = Column(Float, default=3.0)
    max_drawdown_percent = Column(Float, default=10.0)
    consecutive_loss_limit = Column(Integer, default=3)

    bot_enabled = Column(Boolean, default=False)
    auto_trade = Column(Boolean, default=False)
    ai_analysis_enabled = Column(Boolean, default=True)
    ai_analysis_interval = Column(Integer, default=300)

    polymarket_api_key = Column("binance_api_key", String(255), nullable=True)
    polymarket_api_secret = Column("binance_api_secret", String(255), nullable=True)
    use_public_data_only = Column("use_testnet", Boolean, default=True)

    notification_settings = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="settings")

    @property
    def polymarket_api_passphrase(self):
        return (self.notification_settings or {}).get("polymarket_api_passphrase")

    @polymarket_api_passphrase.setter
    def polymarket_api_passphrase(self, value):
        payload = dict(self.notification_settings or {})
        if value:
            payload["polymarket_api_passphrase"] = value
        else:
            payload.pop("polymarket_api_passphrase", None)
        self.notification_settings = payload

    @property
    def scanner_watchlist(self):
        raw = (self.notification_settings or {}).get("scanner_watchlist")
        if isinstance(raw, list) and raw:
            return raw
        if isinstance(raw, str) and raw.strip():
            return [item.strip().upper() for item in raw.split(",") if item.strip()]
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]

    @scanner_watchlist.setter
    def scanner_watchlist(self, value):
        payload = dict(self.notification_settings or {})
        if isinstance(value, str):
            parsed = [item.strip().upper() for item in value.split(",") if item.strip()]
        else:
            parsed = [str(item).strip().upper() for item in (value or []) if str(item).strip()]
        payload["scanner_watchlist"] = parsed or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]
        self.notification_settings = payload

    @property
    def paper_balance(self):
        raw = (self.notification_settings or {}).get("paper_balance")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 10000.0

    @paper_balance.setter
    def paper_balance(self, value):
        payload = dict(self.notification_settings or {})
        try:
            payload["paper_balance"] = float(value)
        except (TypeError, ValueError):
            payload["paper_balance"] = 10000.0
        self.notification_settings = payload

    @property
    def auto_tuning_enabled(self) -> bool:
        return bool((self.notification_settings or {}).get("auto_tuning_enabled", False))

    @auto_tuning_enabled.setter
    def auto_tuning_enabled(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["auto_tuning_enabled"] = bool(value)
        self.notification_settings = payload

    @property
    def tuning_frequency(self) -> str:
        return str((self.notification_settings or {}).get("tuning_frequency", "weekly"))

    @tuning_frequency.setter
    def tuning_frequency(self, value: str):
        allowed = {"daily", "weekly", "monthly"}
        payload = dict(self.notification_settings or {})
        payload["tuning_frequency"] = value if value in allowed else "weekly"
        self.notification_settings = payload

    @property
    def require_manual_approval_for_tuning(self) -> bool:
        return bool((self.notification_settings or {}).get("require_manual_approval_for_tuning", True))

    @require_manual_approval_for_tuning.setter
    def require_manual_approval_for_tuning(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["require_manual_approval_for_tuning"] = bool(value)
        self.notification_settings = payload

    @property
    def defi_enabled(self) -> bool:
        return bool((self.notification_settings or {}).get("defi_enabled", False))

    @defi_enabled.setter
    def defi_enabled(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["defi_enabled"] = bool(value)
        self.notification_settings = payload

    @property
    def defi_network(self) -> str:
        return str((self.notification_settings or {}).get("defi_network", "arbitrum"))

    @defi_network.setter
    def defi_network(self, value: str):
        allowed = {"arbitrum", "optimism", "base", "polygon"}
        payload = dict(self.notification_settings or {})
        payload["defi_network"] = value if value in allowed else "arbitrum"
        self.notification_settings = payload

    @property
    def defi_networks(self) -> list[str]:
        """All networks to trade on. Defaults to [defi_network] for backwards compat."""
        allowed = {"arbitrum", "optimism", "base", "polygon"}
        saved = (self.notification_settings or {}).get("defi_networks")
        if saved and isinstance(saved, list):
            return [n for n in saved if n in allowed] or [self.defi_network]
        return [self.defi_network]

    @defi_networks.setter
    def defi_networks(self, value: list[str]):
        allowed = {"arbitrum", "optimism", "base", "polygon"}
        payload = dict(self.notification_settings or {})
        payload["defi_networks"] = [n for n in value if n in allowed]
        self.notification_settings = payload

    @property
    def defi_wallet_address(self):
        return (self.notification_settings or {}).get("defi_wallet_address")

    @defi_wallet_address.setter
    def defi_wallet_address(self, value):
        payload = dict(self.notification_settings or {})
        if value:
            payload["defi_wallet_address"] = str(value).strip()
        else:
            payload.pop("defi_wallet_address", None)
        self.notification_settings = payload

    @property
    def defi_wallet_private_key_encrypted(self):
        return (self.notification_settings or {}).get("defi_wallet_private_key_encrypted")

    @defi_wallet_private_key_encrypted.setter
    def defi_wallet_private_key_encrypted(self, value):
        payload = dict(self.notification_settings or {})
        if value:
            payload["defi_wallet_private_key_encrypted"] = str(value)
        else:
            payload.pop("defi_wallet_private_key_encrypted", None)
        self.notification_settings = payload

    @property
    def defi_has_private_key(self) -> bool:
        return bool((self.notification_settings or {}).get("defi_wallet_private_key_encrypted"))

    @property
    def defi_trade_percent(self) -> float:
        try:
            return float((self.notification_settings or {}).get("defi_trade_percent", 50.0))
        except (TypeError, ValueError):
            return 50.0

    @defi_trade_percent.setter
    def defi_trade_percent(self, value: float):
        payload = dict(self.notification_settings or {})
        try:
            payload["defi_trade_percent"] = max(1.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            payload["defi_trade_percent"] = 50.0
        self.notification_settings = payload

    @property
    def defi_slippage(self) -> float:
        try:
            return float((self.notification_settings or {}).get("defi_slippage", 0.5))
        except (TypeError, ValueError):
            return 0.5

    @defi_slippage.setter
    def defi_slippage(self, value: float):
        payload = dict(self.notification_settings or {})
        try:
            payload["defi_slippage"] = max(0.1, min(5.0, float(value)))
        except (TypeError, ValueError):
            payload["defi_slippage"] = 0.5
        self.notification_settings = payload

    @property
    def defi_only_scan(self) -> bool:
        return bool((self.notification_settings or {}).get("defi_only_scan", False))

    @defi_only_scan.setter
    def defi_only_scan(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["defi_only_scan"] = bool(value)
        self.notification_settings = payload

    @property
    def defi_stop_loss_percent(self) -> float:
        try:
            return float((self.notification_settings or {}).get("defi_stop_loss_percent", 3.0))
        except (TypeError, ValueError):
            return 3.0

    @defi_stop_loss_percent.setter
    def defi_stop_loss_percent(self, value: float):
        payload = dict(self.notification_settings or {})
        try:
            payload["defi_stop_loss_percent"] = max(0.5, min(50.0, float(value)))
        except (TypeError, ValueError):
            payload["defi_stop_loss_percent"] = 3.0
        self.notification_settings = payload

    @property
    def defi_entry_prices(self) -> dict:
        raw = (self.notification_settings or {}).get("defi_entry_prices", {})
        return raw if isinstance(raw, dict) else {}

    @defi_entry_prices.setter
    def defi_entry_prices(self, value: dict):
        payload = dict(self.notification_settings or {})
        payload["defi_entry_prices"] = value if isinstance(value, dict) else {}
        self.notification_settings = payload

    @property
    def gmx_enabled(self) -> bool:
        return bool((self.notification_settings or {}).get("gmx_enabled", False))

    @gmx_enabled.setter
    def gmx_enabled(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["gmx_enabled"] = bool(value)
        self.notification_settings = payload

    @property
    def gmx_leverage(self) -> float:
        try:
            return float((self.notification_settings or {}).get("gmx_leverage", 2.0))
        except (TypeError, ValueError):
            return 2.0

    @gmx_leverage.setter
    def gmx_leverage(self, value: float):
        payload = dict(self.notification_settings or {})
        try:
            payload["gmx_leverage"] = max(1.1, min(50.0, float(value)))
        except (TypeError, ValueError):
            payload["gmx_leverage"] = 2.0
        self.notification_settings = payload

    @property
    def gmx_collateral_percent(self) -> float:
        try:
            return float((self.notification_settings or {}).get("gmx_collateral_percent", 10.0))
        except (TypeError, ValueError):
            return 10.0

    @gmx_collateral_percent.setter
    def gmx_collateral_percent(self, value: float):
        payload = dict(self.notification_settings or {})
        try:
            payload["gmx_collateral_percent"] = max(1.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            payload["gmx_collateral_percent"] = 10.0
        self.notification_settings = payload

    @property
    def gmx_sl_percent(self) -> float:
        try:
            return float((self.notification_settings or {}).get("gmx_sl_percent", 3.0))
        except (TypeError, ValueError):
            return 3.0

    @gmx_sl_percent.setter
    def gmx_sl_percent(self, value: float):
        payload = dict(self.notification_settings or {})
        try:
            payload["gmx_sl_percent"] = max(0.5, min(50.0, float(value)))
        except (TypeError, ValueError):
            payload["gmx_sl_percent"] = 3.0
        self.notification_settings = payload

    @property
    def gmx_open_positions(self) -> dict:
        """Track entry prices: {symbol: {direction, entry_price, size_usd, collateral_usdc}}"""
        raw = (self.notification_settings or {}).get("gmx_open_positions", {})
        return raw if isinstance(raw, dict) else {}

    @gmx_open_positions.setter
    def gmx_open_positions(self, value: dict):
        payload = dict(self.notification_settings or {})
        payload["gmx_open_positions"] = value if isinstance(value, dict) else {}
        self.notification_settings = payload

    @property
    def real_trade_enabled(self) -> bool:
        return bool((self.notification_settings or {}).get("real_trade_enabled", False))

    @real_trade_enabled.setter
    def real_trade_enabled(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["real_trade_enabled"] = bool(value)
        self.notification_settings = payload

    @property
    def paper_trade_enabled(self) -> bool:
        return bool((self.notification_settings or {}).get("paper_trade_enabled", False))

    @paper_trade_enabled.setter
    def paper_trade_enabled(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["paper_trade_enabled"] = bool(value)
        self.notification_settings = payload

    @property
    def scan_all_coins(self) -> bool:
        return bool((self.notification_settings or {}).get("scan_all_coins", False))

    @scan_all_coins.setter
    def scan_all_coins(self, value: bool):
        payload = dict(self.notification_settings or {})
        payload["scan_all_coins"] = bool(value)
        self.notification_settings = payload

    @property
    def max_scan_coins(self) -> int:
        try:
            return int((self.notification_settings or {}).get("max_scan_coins", 50))
        except (TypeError, ValueError):
            return 50

    @max_scan_coins.setter
    def max_scan_coins(self, value: int):
        payload = dict(self.notification_settings or {})
        try:
            payload["max_scan_coins"] = max(5, int(value))
        except (TypeError, ValueError):
            payload["max_scan_coins"] = 50
        self.notification_settings = payload

    @property
    def min_volume_filter(self) -> float:
        try:
            return float((self.notification_settings or {}).get("min_volume_filter", 5_000_000.0))
        except (TypeError, ValueError):
            return 5_000_000.0

    @min_volume_filter.setter
    def min_volume_filter(self, value: float):
        payload = dict(self.notification_settings or {})
        try:
            payload["min_volume_filter"] = max(0.0, float(value))
        except (TypeError, ValueError):
            payload["min_volume_filter"] = 5_000_000.0
        self.notification_settings = payload
