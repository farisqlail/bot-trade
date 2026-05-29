from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging_config import get_logger
from app.core.security import get_current_user_id
from app.database import AsyncSessionLocal, get_db
from app.models.ai_analysis import AIAnalysis
from app.models.settings import Settings
from app.models.trade import Trade, TradeStatus
from app.services.defi_service import DeFiService, ARBITRUM_KNOWN_TOKENS, _dexscreener_cache
from app.services.exchange_service import ExchangeService

logger = get_logger(__name__)

router = APIRouter(prefix="/chart", tags=["chart"])


# ── EMA helper ────────────────────────────────────────────────────────────────

def _ema(closes: list[float], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = []
    k = 2.0 / (period + 1)
    prev: Optional[float] = None
    for i, c in enumerate(closes):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            seed = sum(closes[:period]) / period
            result.append(seed)
            prev = seed
        else:
            val = c * k + prev * (1 - k)
            result.append(val)
            prev = val
    return result


# ── Schemas ───────────────────────────────────────────────────────────────────

class CandleData(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None


class SignalLevel(BaseModel):
    signal: Optional[str] = None
    confidence: Optional[float] = None
    trend: Optional[str] = None
    analysis_text: Optional[str] = None
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    price_at_signal: Optional[float] = None
    created_at: Optional[str] = None


class ActiveTradeData(BaseModel):
    id: int
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    current_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    status: str


class WatchlistItem(BaseModel):
    symbol: str
    price: float
    change_24h: float
    signal: Optional[str] = None
    confidence: Optional[float] = None
    score: float
    dex_available: bool = False
    dex_network: Optional[str] = None


class ChartBundle(BaseModel):
    symbol: str
    interval: str
    candles: List[CandleData]
    signal: Optional[SignalLevel] = None
    active_trade: Optional[ActiveTradeData] = None
    signal_markers: List[dict] = []


# ── Private helpers ───────────────────────────────────────────────────────────

def _decode_ws_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except (JWTError, Exception):
        return None


def _build_signal(analysis: AIAnalysis) -> SignalLevel:
    entry = analysis.suggested_entry or analysis.price_at_analysis or 0.0
    sl = analysis.suggested_sl or 0.0
    tp1 = analysis.suggested_tp or 0.0

    distance = abs(tp1 - entry) if (entry and tp1) else 0.0
    is_sell = (analysis.recommended_action or "").upper() == "SELL"
    tp2 = (entry - distance * 1.5) if is_sell else (entry + distance * 1.5)
    tp3 = (entry - distance * 2.0) if is_sell else (entry + distance * 2.0)

    return SignalLevel(
        signal=analysis.recommended_action,
        confidence=analysis.confidence,
        trend=analysis.trend,
        analysis_text=analysis.analysis_text,
        entry=entry or None,
        stop_loss=sl or None,
        tp1=tp1 or None,
        tp2=tp2 if tp1 else None,
        tp3=tp3 if tp1 else None,
        price_at_signal=analysis.price_at_analysis,
        created_at=analysis.created_at.isoformat() if analysis.created_at else None,
    )


async def _fetch_candles_with_ema(
    exchange: ExchangeService,
    symbol: str,
    interval: str,
    limit: int,
) -> list[CandleData]:
    try:
        fetch_limit = min(limit + 250, 1000)
        raw = await exchange.get_klines(symbol, interval=interval, limit=fetch_limit)
    except Exception as exc:
        logger.warning("candles_fetch_failed", symbol=symbol, interval=interval, error=str(exc))
        return []

    if not raw:
        return []

    closes = [c["close"] for c in raw]
    ema20_vals = _ema(closes, 20)
    ema50_vals = _ema(closes, 50)
    ema200_vals = _ema(closes, 200)

    all_candles = [
        CandleData(
            time=raw[i]["open_time"] // 1000,
            open=raw[i]["open"],
            high=raw[i]["high"],
            low=raw[i]["low"],
            close=raw[i]["close"],
            volume=raw[i]["volume"],
            ema20=ema20_vals[i],
            ema50=ema50_vals[i],
            ema200=ema200_vals[i],
        )
        for i in range(len(raw))
    ]
    return all_candles[-limit:]


async def _fetch_active_trade(
    db: AsyncSession,
    exchange: ExchangeService,
    user_id: int,
    symbol: str,
) -> Optional[ActiveTradeData]:
    row = (
        await db.execute(
            select(Trade)
            .where(Trade.user_id == user_id, Trade.symbol == symbol, Trade.status == TradeStatus.OPEN)
            .order_by(desc(Trade.opened_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        return None

    current_price = pnl = pnl_percent = None
    try:
        ticker = await exchange.get_ticker(symbol)
        current_price = ticker["price"]
        if str(row.direction).upper() == "LONG":
            pnl = (current_price - row.entry_price) * row.quantity
        else:
            pnl = (row.entry_price - current_price) * row.quantity
        pnl_percent = (pnl / row.risk_amount * 100) if row.risk_amount else None
    except Exception:
        pass

    return ActiveTradeData(
        id=row.id,
        direction=str(row.direction),
        entry_price=row.entry_price,
        stop_loss=row.stop_loss,
        take_profit=row.take_profit,
        current_price=current_price,
        pnl=pnl,
        pnl_percent=pnl_percent,
        status=str(row.status),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/watchlist/ranking", response_model=List[WatchlistItem])
async def get_watchlist_ranking(
    limit: int = Query(30, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        # Use 2h window first (reflects latest scan session); fall back to 24h if empty
        for hours in (2, 24):
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            subq = (
                select(AIAnalysis.symbol, func.max(AIAnalysis.created_at).label("max_ts"))
                .where(AIAnalysis.created_at >= cutoff)
                .group_by(AIAnalysis.symbol)
                .subquery()
            )
            analyses = (
                await db.execute(
                    select(AIAnalysis)
                    .join(subq, (AIAnalysis.symbol == subq.c.symbol) & (AIAnalysis.created_at == subq.c.max_ts))
                    .order_by(desc(AIAnalysis.confidence))
                    .limit(limit * 2)
                )
            ).scalars().all()
            if analyses:
                break
    except Exception as exc:
        logger.warning("watchlist_ranking_db_error", error=str(exc))
        return []

    # Load user's configured DeFi network for DEX availability check
    s_row = (await db.execute(select(Settings).where(Settings.user_id == user_id))).scalar_one_or_none()
    defi_network = (s_row.defi_network if s_row else None) or "arbitrum"
    defi_enabled = s_row.defi_enabled if s_row else False

    exchange = ExchangeService()

    async def _check_dex(symbol: str) -> tuple[bool, str | None]:
        """Fast static check first (Arbitrum known tokens), then cached DexScreener."""
        if not defi_enabled:
            return False, None
        sym = symbol.upper()
        # Instant check: Arbitrum static registry
        if defi_network == "arbitrum" and sym in ARBITRUM_KNOWN_TOKENS:
            return True, "arbitrum"
        # Cache check (no API call if uncached — SpotTradePanel handles full check on click)
        strict_key = f"strict:{defi_network}:{sym}"
        cached = _dexscreener_cache.get(strict_key, "MISS")
        if cached != "MISS":
            return (bool(cached), cached.get("network") if cached else None)
        # Fallback: quick DexScreener lookup (result cached for next request)
        try:
            svc = DeFiService(network=defi_network)
            meta = await svc.get_token_metadata(sym, strict_network=True)
            return (bool(meta), meta.get("network") if meta else None)
        except Exception:
            return False, None

    async def _get_item(a) -> WatchlistItem:
        price = change = 0.0
        try:
            t = await exchange.get_ticker(a.symbol)
            price, change = t["price"], t["change_24h"]
        except Exception:
            pass
        score = float(a.confidence or 0) * (1.0 + abs(change) / 100.0)
        dex_ok, dex_net = await _check_dex(a.symbol)
        return WatchlistItem(
            symbol=a.symbol,
            price=price,
            change_24h=change,
            signal=a.recommended_action,
            confidence=a.confidence,
            score=score,
            dex_available=dex_ok,
            dex_network=dex_net,
        )

    items = await asyncio.gather(*[_get_item(a) for a in analyses])
    items = sorted(items, key=lambda x: x.score, reverse=True)

    # DeFi-only: drop coins not on user's configured network
    if s_row and s_row.defi_enabled and s_row.defi_only_scan:
        items = [i for i in items if i.dex_available]

    return items[:limit]


@router.get("/{symbol}/candles", response_model=List[CandleData])
async def get_candles(
    symbol: str,
    interval: str = Query("60"),
    limit: int = Query(200, ge=10, le=500),
    user_id: int = Depends(get_current_user_id),
):
    exchange = ExchangeService()
    return await _fetch_candles_with_ema(exchange, symbol.upper(), interval, limit)


@router.get("/{symbol}/signal", response_model=Optional[SignalLevel])
async def get_signal(
    symbol: str,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    analysis = (
        await db.execute(
            select(AIAnalysis)
            .where(AIAnalysis.symbol == symbol.upper())
            .order_by(desc(AIAnalysis.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    return _build_signal(analysis) if analysis else None


@router.get("/{symbol}/active-trade", response_model=Optional[ActiveTradeData])
async def get_active_trade(
    symbol: str,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    exchange = ExchangeService()
    return await _fetch_active_trade(db, exchange, user_id, symbol.upper())


@router.get("/{symbol}/analysis", response_model=ChartBundle)
async def get_chart_bundle(
    symbol: str,
    interval: str = Query("60"),
    limit: int = Query(200, ge=10, le=500),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    sym = symbol.upper()
    exchange = ExchangeService()

    # Exchange fetch runs concurrently with DB queries (separate I/O)
    candles_task = asyncio.create_task(
        _fetch_candles_with_ema(exchange, sym, interval, limit)
    )

    analysis = (
        await db.execute(
            select(AIAnalysis).where(AIAnalysis.symbol == sym).order_by(desc(AIAnalysis.created_at)).limit(1)
        )
    ).scalar_one_or_none()

    active_trade = await _fetch_active_trade(db, exchange, user_id, sym)

    markers_rows = (
        await db.execute(
            select(AIAnalysis).where(AIAnalysis.symbol == sym).order_by(desc(AIAnalysis.created_at)).limit(50)
        )
    ).scalars().all()

    candles = await candles_task

    signal_markers = [
        {
            "time": int(a.created_at.timestamp()),
            "action": a.recommended_action,
            "price": a.price_at_analysis,
            "confidence": a.confidence,
        }
        for a in markers_rows
        if (a.recommended_action or "").upper() in ("BUY", "SELL")
        and a.price_at_analysis
        and a.created_at
    ]

    return ChartBundle(
        symbol=sym,
        interval=interval,
        candles=candles,
        signal=_build_signal(analysis) if analysis else None,
        active_trade=active_trade,
        signal_markers=signal_markers,
    )


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/{symbol}")
async def websocket_chart(
    websocket: WebSocket,
    symbol: str,
    token: str = Query(None),
):
    user_id = _decode_ws_token(token or "")
    if user_id is None:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    sym = symbol.upper()
    exchange = ExchangeService()

    try:
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    ticker, raw, analysis = await asyncio.gather(
                        exchange.get_ticker(sym),
                        exchange.get_klines(sym, interval="60", limit=2),
                        db.execute(
                            select(AIAnalysis)
                            .where(AIAnalysis.symbol == sym)
                            .order_by(desc(AIAnalysis.created_at))
                            .limit(1)
                        ),
                    )
                    analysis_row = analysis.scalar_one_or_none()

                payload: dict = {
                    "type": "chart_update",
                    "symbol": sym,
                    "price": ticker["price"],
                    "change_24h": ticker["change_24h"],
                }

                if raw:
                    latest = raw[-1]
                    payload["latest_candle"] = {
                        "time": latest["open_time"] // 1000,
                        "open": latest["open"],
                        "high": latest["high"],
                        "low": latest["low"],
                        "close": latest["close"],
                        "volume": latest["volume"],
                    }

                if analysis_row:
                    payload["signal"] = _build_signal(analysis_row).model_dump()

                await websocket.send_json(payload)
            except WebSocketDisconnect:
                break
            except Exception:
                pass

            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
