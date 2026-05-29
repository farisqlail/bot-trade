from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "tradingbot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scan-market-opportunities": {
            "task": "app.workers.tasks.scan_market_opportunities",
            "schedule": settings.AI_ANALYSIS_INTERVAL,
        },
        "risk-check": {
            "task": "app.workers.tasks.check_risk_limits",
            "schedule": 60.0,
        },
        "check-sl-tp": {
            "task": "app.workers.tasks.check_stop_loss_take_profit",
            "schedule": 30.0,
        },
        "auto-tuning": {
            "task": "app.workers.tasks.run_auto_tuning",
            "schedule": crontab(hour=2, minute=0),  # daily 02:00 UTC, TuningService handles freq logic
        },
        "monitor-defi-positions": {
            "task": "app.workers.tasks.monitor_defi_positions",
            "schedule": 60.0,  # check held DeFi tokens every 60s, auto-exit on SELL signal
        },
        "monitor-bybit-positions": {
            "task": "app.workers.tasks.monitor_bybit_positions",
            "schedule": 60.0,  # sync Bybit positions, signal-exit, move SL to breakeven
        },
        "monitor-gmx-positions": {
            "task": "app.workers.tasks.monitor_gmx_positions",
            "schedule": 60.0,  # check GMX futures positions, stop-loss on price drop
        },
        "check-spot-price-alerts": {
            "task": "app.workers.tasks.check_spot_price_alerts",
            "schedule": 600.0,  # every 10 minutes
        },
    },
)
