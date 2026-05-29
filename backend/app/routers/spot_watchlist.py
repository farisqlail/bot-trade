from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel
from app.database import get_db
from app.core.security import get_current_user_id
from app.models.spot_watchlist import SpotWatchlist
from app.services.spot_market_service import SpotMarketService

router = APIRouter(prefix="/spot-watchlist", tags=["spot-watchlist"])


class SpotWatchlistCreate(BaseModel):
    symbol: str
    contract_address: Optional[str] = None
    network: str = "arbitrum"
    target_buy_price: Optional[float] = None
    target_sell_price: Optional[float] = None
    alert_enabled: bool = True
    notes: Optional[str] = None


class SpotWatchlistUpdate(BaseModel):
    target_buy_price: Optional[float] = None
    target_sell_price: Optional[float] = None
    alert_enabled: Optional[bool] = None
    notes: Optional[str] = None


class SpotWatchlistResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    contract_address: Optional[str] = None
    network: str
    target_buy_price: Optional[float] = None
    target_sell_price: Optional[float] = None
    alert_enabled: bool
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


async def _get_watchlist_items(user_id: int, db: AsyncSession) -> list[SpotWatchlist]:
    result = await db.execute(
        select(SpotWatchlist)
        .where(SpotWatchlist.user_id == user_id)
        .order_by(SpotWatchlist.created_at.desc())
    )
    return result.scalars().all()


@router.get("/", response_model=List[SpotWatchlistResponse])
async def list_watchlist(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await _get_watchlist_items(user_id, db)


@router.post("/", response_model=SpotWatchlistResponse, status_code=201)
async def add_to_watchlist(
    body: SpotWatchlistCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = SpotWatchlist(
        user_id=user_id,
        symbol=body.symbol.upper(),
        contract_address=body.contract_address,
        network=body.network,
        target_buy_price=body.target_buy_price,
        target_sell_price=body.target_sell_price,
        alert_enabled=body.alert_enabled,
        notes=body.notes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=SpotWatchlistResponse)
async def update_watchlist_item(
    item_id: int,
    body: SpotWatchlistUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpotWatchlist).where(SpotWatchlist.id == item_id, SpotWatchlist.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def remove_from_watchlist(
    item_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpotWatchlist).where(SpotWatchlist.id == item_id, SpotWatchlist.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    await db.delete(item)
    await db.commit()


async def _build_price_map(symbols: list[str]) -> dict[str, dict]:
    """Fetch prices from Bybit bulk ticker — same source as altcoin scanner."""
    from app.services.exchange_service import ExchangeService

    if not symbols:
        return {}

    symbol_set = {s.upper() for s in symbols}
    exchange = ExchangeService()
    price_map: dict[str, dict] = {}

    try:
        all_tickers = await exchange.get_all_tickers(min_turnover_usd=0)
        for t in all_tickers:
            # Bybit ticker symbol is e.g. "ARBUSDT"; base symbol is "ARB"
            bybit_sym = t.get("symbol", "")
            base = bybit_sym.replace("USDT", "")
            if base in symbol_set:
                price_map[base] = {
                    "symbol": base,
                    "price": float(t.get("price") or 0),
                    "change_24h": float(t.get("change_24h") or 0),
                    "volume_24h": float(t.get("volume_24h") or 0),
                    "turnover_24h": float(t.get("turnover_24h") or 0),
                }
    except Exception:
        pass

    return price_map


@router.get("/prices")
async def get_watchlist_prices(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    items = await _get_watchlist_items(user_id, db)
    if not items:
        return {"prices": [], "total": 0}

    symbols = [item.symbol for item in items]
    price_map = await _build_price_map(symbols)

    result = []
    for item in items:
        price_data = price_map.get(item.symbol)
        result.append({
            "id": item.id,
            "symbol": item.symbol,
            "network": item.network,
            "target_buy_price": item.target_buy_price,
            "target_sell_price": item.target_sell_price,
            "price": price_data["price"] if price_data else None,
            "change_24h": price_data["change_24h"] if price_data else None,
            "volume_24h": price_data["volume_24h"] if price_data else None,
        })

    return {"prices": result, "total": len(result)}


@router.get("/signals")
async def get_watchlist_signals(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    items = await _get_watchlist_items(user_id, db)
    if not items:
        return {"signals": [], "total": 0}

    symbols = [item.symbol for item in items]
    price_map = await _build_price_map(symbols)

    svc = SpotMarketService()
    signals = []
    for item in items:
        price_data = price_map.get(item.symbol)
        if not price_data:
            signals.append({
                "id": item.id,
                "symbol": item.symbol,
                "signal": "UNKNOWN",
                "reason": "Price data unavailable",
                "price": None,
                "change_24h": None,
                "target_buy_price": item.target_buy_price,
                "target_sell_price": item.target_sell_price,
            })
            continue

        analysis = svc.analyze_spot_signal(item.symbol, price_data)
        analysis["id"] = item.id
        analysis["target_buy_price"] = item.target_buy_price
        analysis["target_sell_price"] = item.target_sell_price
        signals.append(analysis)

    return {"signals": signals, "total": len(signals)}
