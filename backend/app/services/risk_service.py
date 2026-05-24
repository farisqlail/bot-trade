from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone, timedelta
from app.models.risk_event import RiskEvent, RiskEventType, RiskSeverity
from app.models.trade import Trade, TradeStatus
from app.models.settings import Settings
from app.config import settings as app_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RiskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _default_risk_status(self) -> dict:
        return {
            "status": "SAFE",
            "daily_loss_percent": 0.0,
            "daily_loss_limit_percent": 3.0,
            "current_drawdown_percent": 0.0,
            "max_drawdown_percent": 10.0,
            "open_positions": 0,
            "max_open_trades": app_settings.MAX_OPEN_TRADES,
            "consecutive_losses": 0,
            "consecutive_loss_limit": 3,
        }

    async def get_risk_status(self, user_id: int, balance: float) -> dict:
        settings = await self._get_settings(user_id)
        if not settings:
            return self._default_risk_status()

        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        daily_pnl_result = await self.db.execute(
            select(func.sum(Trade.pnl)).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.status == TradeStatus.CLOSED,
                    Trade.closed_at >= today,
                )
            )
        )
        daily_pnl = daily_pnl_result.scalar() or 0.0
        daily_loss_percent = abs(min(daily_pnl, 0)) / balance * 100 if balance > 0 else 0

        open_result = await self.db.execute(
            select(func.count(Trade.id)).where(
                and_(Trade.user_id == user_id, Trade.status == TradeStatus.OPEN)
            )
        )
        open_count = open_result.scalar() or 0

        consecutive_losses = await self._get_consecutive_losses(user_id)

        status = "SAFE"
        if daily_loss_percent >= settings.daily_loss_limit_percent:
            status = "CRITICAL"
        elif daily_loss_percent >= settings.daily_loss_limit_percent * 0.8:
            status = "DANGER"
        elif daily_loss_percent >= settings.daily_loss_limit_percent * 0.5:
            status = "WARNING"

        return {
            "status": status,
            "daily_loss_percent": round(daily_loss_percent, 2),
            "daily_loss_limit_percent": settings.daily_loss_limit_percent,
            "current_drawdown_percent": 0.0,
            "max_drawdown_percent": settings.max_drawdown_percent,
            "open_positions": open_count,
            "max_open_trades": settings.max_open_trades,
            "consecutive_losses": consecutive_losses,
            "consecutive_loss_limit": settings.consecutive_loss_limit,
        }

    async def _get_consecutive_losses(self, user_id: int) -> int:
        result = await self.db.execute(
            select(Trade).where(
                and_(Trade.user_id == user_id, Trade.status == TradeStatus.CLOSED)
            ).order_by(Trade.closed_at.desc()).limit(20)
        )
        trades = result.scalars().all()
        consecutive = 0
        for trade in trades:
            if trade.pnl and trade.pnl < 0:
                consecutive += 1
            else:
                break
        return consecutive

    async def _get_settings(self, user_id: int) -> Settings:
        result = await self.db.execute(
            select(Settings).where(Settings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def check_and_log_risk_events(self, user_id: int, balance: float):
        risk = await self.get_risk_status(user_id, balance)

        if risk["status"] == "CRITICAL":
            await self._log_event(
                user_id, RiskEventType.DAILY_LOSS_LIMIT, RiskSeverity.CRITICAL,
                "Daily loss limit reached",
                f"Daily loss {risk['daily_loss_percent']:.1f}% >= limit {risk['daily_loss_limit_percent']:.1f}%",
                risk["daily_loss_percent"], risk["daily_loss_limit_percent"],
                "Bot trading suspended"
            )

        if risk["consecutive_losses"] >= risk["consecutive_loss_limit"]:
            await self._log_event(
                user_id, RiskEventType.CONSECUTIVE_LOSSES, RiskSeverity.HIGH,
                f"Consecutive losses: {risk['consecutive_losses']}",
                "Maximum consecutive losses reached",
                risk["consecutive_losses"], risk["consecutive_loss_limit"],
                "Manual review required"
            )

    async def _log_event(
        self, user_id: int, event_type: RiskEventType, severity: RiskSeverity,
        title: str, description: str, triggered_value: float,
        threshold_value: float, action_taken: str
    ):
        event = RiskEvent(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            title=title,
            description=description,
            triggered_value=triggered_value,
            threshold_value=threshold_value,
            action_taken=action_taken,
        )
        self.db.add(event)
        await self.db.flush()
        logger.warning("risk_event", type=event_type.value, severity=severity.value,
                       title=title, user_id=user_id)
