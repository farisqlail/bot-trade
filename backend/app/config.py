from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
from typing import List, Union
import json


class Settings(BaseSettings):
    APP_NAME: str = "TradingBot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str
    DATABASE_SYNC_URL: str

    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    POLYMARKET_API_KEY: str = ""
    POLYMARKET_API_SECRET: str = ""
    POLYMARKET_API_PASSPHRASE: str = ""
    POLYMARKET_GAMMA_BASE_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_CLOB_BASE_URL: str = "https://clob.polymarket.com"

    BYBIT_API_KEY: str = ""
    BYBIT_API_SECRET: str = ""
    BYBIT_BASE_URL: str = "https://api.bybit.com"

    DEFAULT_SYMBOL: str = "featured"
    DEFAULT_STOP_LOSS: float = 103500.0
    DEFAULT_TAKE_PROFIT: float = 107000.0
    DEFAULT_RISK_PERCENT: float = 1.0
    MAX_OPEN_TRADES: int = 5
    LEVERAGE: int = 10

    # DeepSeek Cloud API (primary — set DEEPSEEK_API_KEY to use)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Ollama fallback (used when DEEPSEEK_API_KEY is empty)
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "deepseek-r1:7b"

    AI_ANALYSIS_INTERVAL: int = 300

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "/var/log/tradingbot/app.log"

    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    RATE_LIMIT_PER_MINUTE: int = 60
    MAX_LOGIN_ATTEMPTS: int = 5

    PROMETHEUS_ENABLED: bool = True

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [v]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
