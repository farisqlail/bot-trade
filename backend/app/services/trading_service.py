from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from app.models.trade import Trade, TradeStatus, TradeDirection
from app.models.settings import Settings
from app.core.exceptions import (
    RiskLimitExceededError, MaxTradesExceededError, InsufficientBalanceError
)
from app.core.logging_config import get_logger
from app.schemas.trade import TradeCreate, TradeClose

logger = get_logger(__name__)


class TradingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_settings(self, user_id: int) -> Settings:
        result = await self.db.execute(
            select(Settings).where(Settings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_open_trades(self, user_id: int) -> List[Trade]:
        result = await self.db.execute(
            select(Trade).where(
                and_(Trade.user_id == user_id, Trade.status == TradeStatus.OPEN)
            )
        )
        return result.scalars().all()

    async def calculate_position_size(
        self, balance: float, risk_percent: float,
        entry_price: float, stop_loss: float
    ) -> float:
        risk_amount = balance * (risk_percent / 100)
        price_diff = abs(entry_price - stop_loss)
        if price_diff == 0:
            raise ValueError("Entry price and stop loss cannot be equal")
        quantity = risk_amount / price_diff
        return round(quantity, 6)

    async def validate_trade(self, user_id: int, trade_data: TradeCreate, balance: float):
        settings = await self.get_user_settings(user_id)
        if not settings:
            raise ValueError("User settings not found")

        open_trades = await self.get_open_trades(user_id)
        if len(open_trades) >= settings.max_open_trades:
            raise MaxTradesExceededError(len(open_trades), settings.max_open_trades)

        if trade_data.risk_percent > settings.risk_percent * 2:
            raise RiskLimitExceededError(trade_data.risk_percent, settings.risk_percent * 2)

        risk_amount = balance * (trade_data.risk_percent / 100)
        if risk_amount > balance * 0.1:
            raise InsufficientBalanceError(risk_amount, balance)

    async def create_trade(
        self, user_id: int, trade_data: TradeCreate, balance: float
    ) -> Trade:
        await self.validate_trade(user_id, trade_data, balance)

        quantity = await self.calculate_position_size(
            balance, trade_data.risk_percent,
            trade_data.entry_price, trade_data.stop_loss
        )
        risk_amount = balance * (trade_data.risk_percent / 100)

        trade = Trade(
            user_id=user_id,
            symbol=trade_data.symbol,
            direction=trade_data.direction,
            status=TradeStatus.OPEN,
            entry_price=trade_data.entry_price,
            stop_loss=trade_data.stop_loss,
            take_profit=trade_data.take_profit,
            quantity=quantity,
            leverage=trade_data.leverage,
            risk_amount=risk_amount,
            risk_percent=trade_data.risk_percent,
            signal_id=trade_data.signal_id,
            notes=trade_data.notes,
            opened_at=datetime.now(timezone.utc),
        )
        self.db.add(trade)
        await self.db.flush()
        await self.db.refresh(trade)

        logger.info("trade_created", trade_id=trade.id, user_id=user_id,
                    symbol=trade.symbol, direction=trade.direction.value)
        return trade

    async def close_trade(self, trade_id: int, user_id: int, close_data: TradeClose) -> Trade:
        result = await self.db.execute(
            select(Trade).where(and_(Trade.id == trade_id, Trade.user_id == user_id))
        )
        trade = result.scalar_one_or_none()
        if not trade:
            raise ValueError("Trade not found")
        if trade.status != TradeStatus.OPEN:
            raise ValueError(f"Trade is not open, status: {trade.status}")

        exit_price = close_data.exit_price
        if trade.direction == TradeDirection.LONG:
            pnl = (exit_price - trade.entry_price) * trade.quantity * trade.leverage
        else:
            pnl = (trade.entry_price - exit_price) * trade.quantity * trade.leverage

        pnl_percent = (pnl / trade.risk_amount) * 100

        trade.exit_price = exit_price
        trade.pnl = round(pnl, 2)
        trade.pnl_percent = round(pnl_percent, 2)
        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.now(timezone.utc)
        if close_data.notes:
            trade.notes = close_data.notes

        await self.db.flush()
        logger.info("trade_closed", trade_id=trade.id, pnl=trade.pnl, pnl_percent=trade.pnl_percent)
        return trade

    async def get_trade_stats(self, user_id: int) -> dict:
        result = await self.db.execute(
            select(Trade).where(
                and_(Trade.user_id == user_id, Trade.status == TradeStatus.CLOSED)
            )
        )
        trades = result.scalars().all()

        if not trades:
            return {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "profit_factor": 0.0, "max_drawdown": 0.0,
                "best_trade": 0.0, "worst_trade": 0.0, "total_pnl": 0.0,
            }

        pnl_values = [t.pnl for t in trades if t.pnl is not None]
        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p < 0]
        total_win = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0

        return {
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
            "avg_win": round(total_win / len(wins), 2) if wins else 0.0,
            "avg_loss": round(total_loss / len(losses), 2) if losses else 0.0,
            "profit_factor": round(total_win / total_loss, 2) if total_loss > 0 else 0.0,
            "max_drawdown": 0.0,
            "best_trade": round(max(pnl_values, default=0.0), 2),
            "worst_trade": round(min(pnl_values, default=0.0), 2),
            "total_pnl": round(sum(pnl_values), 2),
        }

    async def get_pnl_by_period(self, user_id: int) -> dict:
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = day_start - timedelta(days=day_start.weekday())
        month_start = day_start.replace(day=1)

        async def sum_pnl(since: datetime) -> float:
            result = await self.db.execute(
                select(func.sum(Trade.pnl)).where(
                    and_(
                        Trade.user_id == user_id,
                        Trade.status == TradeStatus.CLOSED,
                        Trade.closed_at >= since,
                    )
                )
            )
            return result.scalar() or 0.0

        daily = await sum_pnl(day_start)
        weekly = await sum_pnl(week_start)
        monthly = await sum_pnl(month_start)

        return {
            "daily_pnl": round(daily, 2),
            "weekly_pnl": round(weekly, 2),
            "monthly_pnl": round(monthly, 2),
        }
