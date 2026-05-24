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
    },
)
