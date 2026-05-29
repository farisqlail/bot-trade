try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import make_asgi_app

from app.config import settings
from app.core.logging_config import setup_logging
from app.core.exceptions import (
    TradingBotException, trading_bot_exception_handler,
    validation_exception_handler, generic_exception_handler,
)
from app.routers import auth, dashboard, trades, ai_analysis, risk, bot, tuning, chart
from app.routers import defi, gmx, gtrade, bybit_futures, webhook
from app.routers import spot_trades, spot_watchlist

setup_logging()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(TradingBotException, trading_bot_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else settings.ALLOWED_HOSTS if hasattr(settings, "ALLOWED_HOSTS") else ["*"],
)

API_PREFIX = settings.API_V1_STR
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(trades.router, prefix=API_PREFIX)
app.include_router(ai_analysis.router, prefix=API_PREFIX)
app.include_router(risk.router, prefix=API_PREFIX)
app.include_router(bot.router, prefix=API_PREFIX)
app.include_router(tuning.router, prefix=API_PREFIX)
app.include_router(chart.router, prefix=API_PREFIX)
app.include_router(defi.router, prefix=API_PREFIX)
app.include_router(gmx.router, prefix=API_PREFIX)
app.include_router(gtrade.router, prefix=API_PREFIX)
app.include_router(bybit_futures.router, prefix=API_PREFIX)
app.include_router(webhook.router, prefix=API_PREFIX)
app.include_router(spot_trades.router, prefix=API_PREFIX)
app.include_router(spot_watchlist.router, prefix=API_PREFIX)

if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


@app.on_event("startup")
async def register_telegram_webhook():
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_WEBHOOK_URL:
        return
    import httpx
    from app.core.logging_config import get_logger
    _log = get_logger(__name__)
    params: dict = {"url": settings.TELEGRAM_WEBHOOK_URL}
    if settings.TELEGRAM_WEBHOOK_SECRET:
        params["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook",
                json=params,
            )
            data = resp.json()
            if data.get("ok"):
                _log.info("telegram_webhook_registered", url=settings.TELEGRAM_WEBHOOK_URL)
            else:
                _log.warning("telegram_webhook_register_failed", result=data)
    except Exception as exc:
        _log.warning("telegram_webhook_setup_error", error=str(exc))


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
