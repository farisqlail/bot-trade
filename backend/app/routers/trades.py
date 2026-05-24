from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional
from app.database import get_db
from app.core.security import get_current_user_id
from app.services.trading_service import TradingService
from app.services.exchange_service import ExchangeService
from app.models.trade import Trade, TradeStatus
from app.schemas.trade import TradeCreate, TradeResponse, TradeUpdate, TradeClose

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("", response_model=TradeResponse, status_code=201)
async def create_trade(
    trade_data: TradeCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    exchange_svc = ExchangeService()
    account = await exchange_svc.get_account_balance()
    trading_svc = TradingService(db)
    user_settings = await trading_svc.get_user_settings(user_id)
    balance = user_settings.paper_balance if user_settings else account["balance"]
    trade = await trading_svc.create_trade(user_id, trade_data, balance)
    return trade


@router.get("/open", response_model=List[TradeResponse])
async def get_open_trades(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    trading_svc = TradingService(db)
    return await trading_svc.get_open_trades(user_id)


@router.get("/history", response_model=List[TradeResponse])
async def get_trade_history(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    symbol: Optional[str] = None,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    filters = [Trade.user_id == user_id, Trade.status == TradeStatus.CLOSED]
    if symbol:
        filters.append(Trade.symbol == symbol)
    result = await db.execute(
        select(Trade).where(and_(*filters))
        .order_by(desc(Trade.closed_at))
        .limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trade).where(and_(Trade.id == trade_id, Trade.user_id == user_id))
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.patch("/{trade_id}", response_model=TradeResponse)
async def update_trade(
    trade_id: int,
    update_data: TradeUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trade).where(and_(Trade.id == trade_id, Trade.user_id == user_id))
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != TradeStatus.OPEN:
        raise HTTPException(status_code=400, detail="Can only update open trades")

    if update_data.stop_loss is not None:
        trade.stop_loss = update_data.stop_loss
    if update_data.take_profit is not None:
        trade.take_profit = update_data.take_profit
    if update_data.notes is not None:
        trade.notes = update_data.notes

    await db.flush()
    await db.refresh(trade)
    return trade


@router.post("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: int,
    close_data: TradeClose,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    trading_svc = TradingService(db)
    try:
        return await trading_svc.close_trade(trade_id, user_id, close_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
