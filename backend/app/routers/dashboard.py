from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.database import get_db
from app.config import settings
from app.core.security import get_current_user_id
from app.services.trading_service import TradingService
from app.services.risk_service import RiskService
from app.services.exchange_service import ExchangeService
from app.schemas.dashboard import DashboardResponse, AccountMetrics, PnLMetrics, TradeMetrics, RiskStatus, BotStatus
from sqlalchemy import select
from app.models.settings import Settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    trading_svc = TradingService(db)
    risk_svc = RiskService(db)
    exchange_svc = ExchangeService()

    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    user_settings = result.scalar_one_or_none()
    account_data = await exchange_svc.get_account_balance()
    if user_settings:
        account_data["balance"] = user_settings.paper_balance
        account_data["equity"] = user_settings.paper_balance + account_data.get("unrealized_pnl", 0.0)
        account_data["free_margin"] = user_settings.paper_balance
    balance = account_data["balance"]

    stats = await trading_svc.get_trade_stats(user_id)
    pnl_data = await trading_svc.get_pnl_by_period(user_id)
    risk_data = await risk_svc.get_risk_status(user_id, balance)

    open_trades = await trading_svc.get_open_trades(user_id)
    unrealized_pnl = sum(
        0.0 for t in open_trades
    )

    account = AccountMetrics(
        balance=account_data["balance"],
        equity=account_data["equity"],
        unrealized_pnl=account_data.get("unrealized_pnl", 0.0),
        margin_used=account_data.get("margin_used", 0.0),
        free_margin=account_data.get("free_margin", account_data["balance"]),
    )

    pnl = PnLMetrics(
        daily_pnl=pnl_data["daily_pnl"],
        daily_pnl_percent=round(pnl_data["daily_pnl"] / balance * 100, 2) if balance else 0,
        weekly_pnl=pnl_data["weekly_pnl"],
        weekly_pnl_percent=round(pnl_data["weekly_pnl"] / balance * 100, 2) if balance else 0,
        monthly_pnl=pnl_data["monthly_pnl"],
        monthly_pnl_percent=round(pnl_data["monthly_pnl"] / balance * 100, 2) if balance else 0,
        total_pnl=stats.get("total_pnl", 0.0),
    )

    trades = TradeMetrics(
        total_trades=stats["total_trades"],
        winning_trades=stats["winning_trades"],
        losing_trades=stats["losing_trades"],
        win_rate=stats["win_rate"],
        avg_win=stats["avg_win"],
        avg_loss=stats["avg_loss"],
        profit_factor=stats["profit_factor"],
        max_drawdown=stats["max_drawdown"],
        best_trade=stats["best_trade"],
        worst_trade=stats["worst_trade"],
    )

    risk = RiskStatus(**risk_data)

    bot = BotStatus(
        is_running=user_settings.bot_enabled if user_settings else False,
        auto_trade=user_settings.auto_trade if user_settings else False,
        ai_enabled=user_settings.ai_analysis_enabled if user_settings else False,
        symbol=user_settings.symbol if user_settings else settings.DEFAULT_SYMBOL,
    )

    return DashboardResponse(
        account=account,
        pnl=pnl,
        trades=trades,
        risk=risk,
        bot=bot,
        last_updated=datetime.now(timezone.utc),
    )
