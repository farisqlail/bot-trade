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
