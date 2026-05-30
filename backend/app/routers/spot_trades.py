from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel
from app.database import get_db
from app.core.security import get_current_user_id
from app.models.spot_trade import SpotTrade, SpotTradeType, SpotTradeStatus

router = APIRouter(prefix="/spot-trades", tags=["spot-trades"])


class SpotTradeCreate(BaseModel):
    symbol: str
    base_token: str
    quote_token: str
    trade_type: SpotTradeType
    amount_in: float
    price_at_trade: float
    price_target: Optional[float] = None
    notes: Optional[str] = None


class SpotTradeUpdate(BaseModel):
    amount_out: Optional[float] = None
    price_at_trade: Optional[float] = None
    status: Optional[SpotTradeStatus] = None
    tx_hash: Optional[str] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None


class SpotTradeResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    base_token: str
    quote_token: str
    trade_type: SpotTradeType
    status: SpotTradeStatus
    amount_in: float
    amount_out: Optional[float] = None
    price_at_trade: Optional[float] = None
    price_target: Optional[float] = None
    tx_hash: Optional[str] = None
    network: str
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    notes: Optional[str] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


@router.get("/stats/summary")
async def get_stats_summary(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpotTrade).where(SpotTrade.user_id == user_id)
    )
    trades = result.scalars().all()

    if not trades:
        return {
            "total_trades": 0,
            "total_invested": 0.0,
            "current_value": 0.0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "best_trade": None,
            "worst_trade": None,
        }

    completed = [t for t in trades if t.status == SpotTradeStatus.COMPLETED and t.pnl is not None]
    active = [t for t in trades if t.status == SpotTradeStatus.COMPLETED]
    total_invested = sum(t.amount_in for t in active)
    total_pnl = sum(t.pnl for t in completed)
    current_value = total_invested + total_pnl

    wins = [t for t in completed if t.pnl > 0]
    win_rate = len(wins) / len(completed) if completed else 0.0

    best = max(completed, key=lambda t: t.pnl, default=None)
    worst = min(completed, key=lambda t: t.pnl, default=None)

    return {
        "total_trades": len(active),
        "total_invested": round(total_invested, 6),
        "current_value": round(current_value, 6),
        "total_pnl": round(total_pnl, 6),
        "win_rate": round(win_rate, 4),
        "best_trade": {
            "id": best.id,
            "symbol": best.symbol,
            "pnl": best.pnl,
            "pnl_percent": best.pnl_percent,
        } if best else None,
        "worst_trade": {
            "id": worst.id,
            "symbol": worst.symbol,
            "pnl": worst.pnl,
            "pnl_percent": worst.pnl_percent,
        } if worst else None,
    }


@router.get("/", response_model=List[SpotTradeResponse])
async def list_spot_trades(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpotTrade)
        .where(SpotTrade.user_id == user_id)
        .order_by(SpotTrade.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/", response_model=SpotTradeResponse, status_code=201)
async def create_spot_trade(
    body: SpotTradeCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    trade = SpotTrade(
        user_id=user_id,
        symbol=body.symbol.upper(),
        base_token=body.base_token.upper(),
        quote_token=body.quote_token.upper(),
        trade_type=body.trade_type,
        amount_in=body.amount_in,
        price_at_trade=body.price_at_trade,
        price_target=body.price_target,
        notes=body.notes,
        opened_at=datetime.now(timezone.utc),
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return trade


@router.get("/{trade_id}", response_model=SpotTradeResponse)
async def get_spot_trade(
    trade_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpotTrade).where(SpotTrade.id == trade_id, SpotTrade.user_id == user_id)
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.put("/{trade_id}", response_model=SpotTradeResponse)
async def update_spot_trade(
    trade_id: int,
    body: SpotTradeUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpotTrade).where(SpotTrade.id == trade_id, SpotTrade.user_id == user_id)
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(trade, field, value)

    if body.status == SpotTradeStatus.COMPLETED and not trade.closed_at:
        trade.closed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(trade)
    return trade


@router.delete("/{trade_id}", status_code=204)
async def delete_spot_trade(
    trade_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpotTrade).where(SpotTrade.id == trade_id, SpotTrade.user_id == user_id)
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    await db.delete(trade)
    await db.commit()
