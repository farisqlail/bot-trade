import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.models.settings import Settings
from app.models.trade import Trade, TradeStatus
from app.models.tuning import TuningHistory
from app.core.logging_config import get_logger

logger = get_logger(__name__)

MIN_RISK = 0.1
MAX_RISK = 5.0
MIN_TRADES_REQUIRED = 5
ANALYSIS_PERIOD_DAYS = 30


class TuningService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_settings(self, user_id: int) -> Settings | None:
        result = await self.db.execute(select(Settings).where(Settings.user_id == user_id))
        return result.scalar_one_or_none()

    async def _get_recent_trades(self, user_id: int, period_days: int = ANALYSIS_PERIOD_DAYS) -> list[Trade]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        result = await self.db.execute(
            select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.status == TradeStatus.CLOSED,
                    Trade.created_at >= cutoff,
                )
            ).order_by(Trade.created_at)
        )
        return result.scalars().all()

    async def _get_last_tuning(self, user_id: int) -> TuningHistory | None:
        result = await self.db.execute(
            select(TuningHistory)
            .where(TuningHistory.user_id == user_id)
            .order_by(desc(TuningHistory.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _compute_metrics(self, trades: list[Trade]) -> dict:
        if not trades:
            return {"total_trades": 0}

        pnl_values = [t.pnl for t in trades if t.pnl is not None]
        if not pnl_values:
            return {"total_trades": len(trades), "win_rate": 0, "profit_factor": 0}

        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p <= 0]
        win_rate = len(wins) / len(pnl_values)

        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = sum(wins) / gross_loss if gross_loss > 0 else (99.0 if wins else 0.0)

        # Max consecutive losses
        max_cl = cur_cl = 0
        for p in pnl_values:
            if p <= 0:
                cur_cl += 1
                max_cl = max(max_cl, cur_cl)
            else:
                cur_cl = 0

        return {
            "total_trades": len(pnl_values),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(min(profit_factor, 99.0), 4),
            "max_consecutive_losses": max_cl,
            "avg_pnl": round(sum(pnl_values) / len(pnl_values), 4),
            "period_days": ANALYSIS_PERIOD_DAYS,
        }

    def _recommend(self, metrics: dict, settings: Settings) -> tuple[float, str]:
        """Returns (new_risk_percent, reason_str). reason empty = no change."""
        total = metrics.get("total_trades", 0)
        if total < MIN_TRADES_REQUIRED:
            return settings.risk_percent, ""

        current = settings.risk_percent
        win_rate = metrics.get("win_rate", 0.5)
        pf = metrics.get("profit_factor", 1.0)
        max_cl = metrics.get("max_consecutive_losses", 0)
        consec_limit = settings.consecutive_loss_limit

        # Decrease triggers
        if win_rate < 0.35:
            new = max(MIN_RISK, round(current - 0.2, 2))
            if new == current:
                return current, ""
            return new, f"Win rate {win_rate*100:.0f}% < 35% threshold — reduce risk."

        if max_cl >= consec_limit:
            new = max(MIN_RISK, round(current - 0.15, 2))
            if new == current:
                return current, ""
            return new, f"{max_cl} consecutive losses hit limit ({consec_limit}) — reduce risk."

        # Increase trigger
        if win_rate >= 0.60 and pf >= 1.5 and total >= 10:
            new = min(MAX_RISK, round(current + 0.1, 2))
            if new == current:
                return current, ""
            return new, f"Win rate {win_rate*100:.0f}%, PF {pf:.2f} — strong performance, increase risk."

        return current, ""

    def _should_run(self, settings: Settings, last_tuning: TuningHistory | None) -> bool:
        if not settings.auto_tuning_enabled:
            return False
        if last_tuning is None:
            return True
        freq = settings.tuning_frequency
        delta_map = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}
        required_gap = delta_map.get(freq, timedelta(days=7))
        last_run = last_tuning.created_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_run >= required_gap

    async def run_tuning(self, user_id: int) -> TuningHistory | None:
        """Analyze performance and create TuningHistory record. Returns None if no action needed."""
        s = await self._get_settings(user_id)
        if not s:
            logger.warning("tuning_settings_not_found", user_id=user_id)
            return None

        last = await self._get_last_tuning(user_id)

        if not self._should_run(s, last):
            logger.info("tuning_skipped_frequency", user_id=user_id, freq=s.tuning_frequency)
            return None

        # Check if there's already a pending approval
        if last and last.status == "pending":
            logger.info("tuning_skipped_pending_exists", user_id=user_id, tuning_id=last.id)
            return None

        trades = await self._get_recent_trades(user_id)
        metrics = self._compute_metrics(trades)
        new_risk, reason = self._recommend(metrics, s)

        if not reason:
            record = TuningHistory(
                user_id=user_id,
                status="skipped",
                old_risk_percent=s.risk_percent,
                new_risk_percent=s.risk_percent,
                change_direction="no_change",
                reason=f"No adjustment needed. Trades analyzed: {metrics.get('total_trades', 0)}",
                metrics_snapshot=metrics,
                approval_token=secrets.token_urlsafe(32),
            )
            self.db.add(record)
            await self.db.flush()
            logger.info("tuning_no_change", user_id=user_id, metrics=metrics)
            return None

        direction = "increase" if new_risk > s.risk_percent else "decrease"
        status = "pending" if s.require_manual_approval_for_tuning else "auto_applied"

        record = TuningHistory(
            user_id=user_id,
            status=status,
            old_risk_percent=s.risk_percent,
            new_risk_percent=new_risk,
            change_direction=direction,
            reason=reason,
            metrics_snapshot=metrics,
            approval_token=secrets.token_urlsafe(32),
        )
        self.db.add(record)

        if not s.require_manual_approval_for_tuning:
            s.risk_percent = new_risk
            record.resolved_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(record)
        logger.info(
            "tuning_recommendation",
            user_id=user_id,
            old=s.risk_percent if s.require_manual_approval_for_tuning else record.old_risk_percent,
            new=new_risk,
            direction=direction,
            status=status,
        )
        return record

    async def approve(self, tuning_id: int, user_id: int) -> TuningHistory:
        result = await self.db.execute(
            select(TuningHistory).where(
                and_(TuningHistory.id == tuning_id, TuningHistory.user_id == user_id)
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            raise ValueError(f"TuningHistory {tuning_id} not found")
        if record.status != "pending":
            raise ValueError(f"TuningHistory {tuning_id} is not pending (status={record.status})")

        s = await self._get_settings(user_id)
        if s:
            s.risk_percent = record.new_risk_percent

        record.status = "approved"
        record.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(record)
        logger.info("tuning_approved", tuning_id=tuning_id, new_risk=record.new_risk_percent)
        return record

    async def reject(self, tuning_id: int, user_id: int) -> TuningHistory:
        result = await self.db.execute(
            select(TuningHistory).where(
                and_(TuningHistory.id == tuning_id, TuningHistory.user_id == user_id)
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            raise ValueError(f"TuningHistory {tuning_id} not found")
        if record.status != "pending":
            raise ValueError(f"TuningHistory {tuning_id} is not pending (status={record.status})")

        record.status = "rejected"
        record.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(record)
        logger.info("tuning_rejected", tuning_id=tuning_id)
        return record

    async def approve_by_token(self, token: str) -> TuningHistory | None:
        result = await self.db.execute(
            select(TuningHistory).where(TuningHistory.approval_token == token)
        )
        record = result.scalar_one_or_none()
        if not record or record.status != "pending":
            return None
        return await self.approve(record.id, record.user_id)

    async def reject_by_token(self, token: str) -> TuningHistory | None:
        result = await self.db.execute(
            select(TuningHistory).where(TuningHistory.approval_token == token)
        )
        record = result.scalar_one_or_none()
        if not record or record.status != "pending":
            return None
        return await self.reject(record.id, record.user_id)

    async def get_history(self, user_id: int, limit: int = 20) -> list[TuningHistory]:
        result = await self.db.execute(
            select(TuningHistory)
            .where(TuningHistory.user_id == user_id)
            .order_by(desc(TuningHistory.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_pending(self, user_id: int) -> TuningHistory | None:
        result = await self.db.execute(
            select(TuningHistory).where(
                and_(TuningHistory.user_id == user_id, TuningHistory.status == "pending")
            ).order_by(desc(TuningHistory.created_at)).limit(1)
        )
        return result.scalar_one_or_none()
