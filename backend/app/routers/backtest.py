from fastapi import APIRouter, Depends, Query
from app.core.security import get_current_user_id
from app.services.backtesting_service import BacktestingService

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("")
async def run_backtest(
    symbol: str = Query("BTCUSDT"),
    days: int = Query(30, ge=7, le=90),
    interval: str = Query("60"),
    sl_percent: float = Query(1.5, ge=0.1, le=20.0),
    tp_percent: float = Query(3.0, ge=0.1, le=50.0),
    initial_balance: float = Query(10000.0, ge=100.0),
    risk_percent: float = Query(1.0, ge=0.1, le=10.0),
    user_id: int = Depends(get_current_user_id),
):
    svc = BacktestingService()
    return await svc.run_backtest(
        symbol=symbol.upper(),
        days=days,
        interval=interval,
        sl_percent=sl_percent,
        tp_percent=tp_percent,
        initial_balance=initial_balance,
        risk_percent=risk_percent,
    )
