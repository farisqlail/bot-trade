"""
General-purpose WebSocket endpoint: /api/v1/ws

Client authenticates via ?token=<JWT> query param (same as chart WS).
Subscribe via: {"action": "subscribe", "channels": [...], "symbols": [...]}

Channels and push intervals (base tick = 5s):
  prices          - Bybit ticker for subscribed symbols   (every 5s)
  trades          - open paper/real trades for user       (every 15s, tick%3)
  dashboard       - PnL + risk summary                   (every 30s, tick%6)
  spot_signals    - spot watchlist prices + signals      (every 60s, tick%12)
  gmx_positions   - GMX open positions with live PnL     (every 15s, tick%3)
  gtrade_positions - gTrade open positions with live PnL (every 15s, tick%3)
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings
from app.core.logging_config import get_logger
from app.database import AsyncSessionLocal
from app.services.exchange_service import ExchangeService

logger = get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

TICK_INTERVAL = 5  # seconds


def _decode_ws_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except (JWTError, Exception):
        return None


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None),
):
    user_id = _decode_ws_token(token or "")
    if user_id is None:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    logger.info("ws_connected", user_id=user_id)

    channels: set[str] = set()
    symbols: list[str] = []
    exchange = ExchangeService()

    async def _safe_send(channel: str, data: dict) -> None:
        try:
            await websocket.send_json({"channel": channel, "data": data})
        except Exception:
            pass

    async def _push_prices() -> None:
        if not symbols:
            return
        results = []
        tasks = [exchange.get_ticker(sym) for sym in symbols[:20]]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        for item in raw:
            if isinstance(item, dict):
                results.append(item)
        if results:
            await _safe_send("prices", {"prices": results})

    async def _push_trades() -> None:
        from sqlalchemy import select, and_
        from app.models.trade import Trade, TradeStatus

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Trade).where(
                    and_(Trade.user_id == user_id, Trade.status == TradeStatus.OPEN)
                )
            )
            open_trades = result.scalars().all()

        trades_data = [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": str(t.direction),
                "entry_price": t.entry_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "quantity": t.quantity,
                "leverage": t.leverage,
                "status": str(t.status),
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            }
            for t in open_trades
        ]
        await _safe_send("trades", {"trades": trades_data})

    async def _push_dashboard() -> None:
        from sqlalchemy import select, func, and_
        from app.models.settings import Settings
        from app.models.trade import Trade, TradeStatus
        from app.services.risk_service import RiskService
        from datetime import datetime, timezone, timedelta

        async with AsyncSessionLocal() as db:
            s_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
            s = s_result.scalar_one_or_none()
            balance = s.paper_balance if s else 10000.0

            # Trade stats
            trades_result = await db.execute(
                select(Trade).where(
                    and_(Trade.user_id == user_id, Trade.status == TradeStatus.CLOSED)
                )
            )
            closed_trades = trades_result.scalars().all()
            pnl_values = [t.pnl for t in closed_trades if t.pnl is not None]
            wins = [p for p in pnl_values if p > 0]
            total_pnl = round(sum(pnl_values), 2)
            win_rate = round(len(wins) / len(pnl_values) * 100, 2) if pnl_values else 0.0

            # Period PnL
            now = datetime.now(timezone.utc)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = day_start - timedelta(days=day_start.weekday())

            daily_result = await db.execute(
                select(func.sum(Trade.pnl)).where(
                    and_(
                        Trade.user_id == user_id,
                        Trade.status == TradeStatus.CLOSED,
                        Trade.closed_at >= day_start,
                    )
                )
            )
            daily_pnl = round(daily_result.scalar() or 0.0, 2)

            weekly_result = await db.execute(
                select(func.sum(Trade.pnl)).where(
                    and_(
                        Trade.user_id == user_id,
                        Trade.status == TradeStatus.CLOSED,
                        Trade.closed_at >= week_start,
                    )
                )
            )
            weekly_pnl = round(weekly_result.scalar() or 0.0, 2)

            # Open positions count
            open_result = await db.execute(
                select(func.count(Trade.id)).where(
                    and_(Trade.user_id == user_id, Trade.status == TradeStatus.OPEN)
                )
            )
            open_positions = open_result.scalar() or 0

            # Risk status
            risk_svc = RiskService(db)
            risk_data = await risk_svc.get_risk_status(user_id, balance)

        await _safe_send("dashboard", {
            "balance": balance,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "daily_pnl": daily_pnl,
            "weekly_pnl": weekly_pnl,
            "open_positions": open_positions,
            "risk_status": risk_data.get("status", "SAFE"),
            "daily_loss_percent": risk_data.get("daily_loss_percent", 0.0),
            "current_drawdown_percent": risk_data.get("current_drawdown_percent", 0.0),
            "consecutive_losses": risk_data.get("consecutive_losses", 0),
        })

    async def _push_gmx_positions() -> None:
        from sqlalchemy import select
        from app.models.settings import Settings

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Settings).where(Settings.user_id == user_id))
            s = result.scalar_one_or_none()
        if not s:
            return

        positions = []
        for symbol, pos in (s.gmx_open_positions or {}).items():
            entry_price = float(pos.get("entry_price", 0))
            size_usd = float(pos.get("size_usd", 0))
            collateral = float(pos.get("collateral_usdc", 0))
            is_long = bool(pos.get("is_long", True))
            current_price = pnl_usd = pnl_percent = None
            try:
                ticker = await exchange.get_ticker(symbol)
                current_price = ticker["price"]
                if entry_price > 0 and size_usd > 0:
                    pct = (current_price - entry_price) / entry_price if is_long else (entry_price - current_price) / entry_price
                    pnl_percent = round(pct * 100, 2)
                    pnl_usd = round(pct * size_usd, 2)
            except Exception:
                pass
            positions.append({
                "symbol": symbol,
                "direction": "LONG" if is_long else "SHORT",
                "entry_price": entry_price,
                "current_price": current_price,
                "size_usd": size_usd,
                "collateral_usdc": collateral,
                "leverage": round(size_usd / collateral, 1) if collateral > 0 else None,
                "pnl_usd": pnl_usd,
                "pnl_percent": pnl_percent,
                "opened_at": pos.get("opened_at"),
            })
        await _safe_send("gmx_positions", {
            "positions": positions,
            "gmx_enabled": s.gmx_enabled,
        })

    async def _push_gtrade_positions() -> None:
        from sqlalchemy import select
        from app.models.settings import Settings

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Settings).where(Settings.user_id == user_id))
            s = result.scalar_one_or_none()
        if not s:
            return

        positions = []
        for symbol, pos in (s.gtrade_open_trades or {}).items():
            entry_price = float(pos.get("entry_price", 0))
            size_usd = float(pos.get("size_usd", 0))
            collateral = float(pos.get("collateral_usdc", 0))
            is_long = bool(pos.get("is_long", True))
            current_price = pnl_usd = pnl_percent = None
            try:
                ticker = await exchange.get_ticker(symbol.replace("/", ""))
                current_price = ticker["price"]
                if entry_price > 0 and size_usd > 0:
                    pct = (current_price - entry_price) / entry_price if is_long else (entry_price - current_price) / entry_price
                    pnl_percent = round(pct * 100, 2)
                    pnl_usd = round(pct * size_usd, 2)
            except Exception:
                pass
            positions.append({
                "symbol": symbol,
                "direction": "LONG" if is_long else "SHORT",
                "entry_price": entry_price,
                "current_price": current_price,
                "size_usd": size_usd,
                "collateral_usdc": collateral,
                "leverage": round(size_usd / collateral, 1) if collateral > 0 else None,
                "pnl_usd": pnl_usd,
                "pnl_percent": pnl_percent,
                "tp_price": pos.get("tp_price"),
                "sl_price": pos.get("sl_price"),
                "pair_index": pos.get("pair_index"),
                "trade_index": pos.get("trade_index", 0),
            })
        await _safe_send("gtrade_positions", {
            "positions": positions,
            "gtrade_enabled": s.gtrade_enabled,
        })

    async def _push_spot_signals() -> None:
        from sqlalchemy import select
        from app.models.spot_watchlist import SpotWatchlist
        from app.services.spot_market_service import SpotMarketService

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SpotWatchlist).where(SpotWatchlist.user_id == user_id)
            )
            items = result.scalars().all()

        if not items:
            return

        spot_svc = SpotMarketService()
        syms = [i.symbol for i in items]
        prices = await spot_svc.get_multiple_prices(syms)
        price_map = {p["symbol"]: p for p in prices}

        signals_out = []
        for item in items:
            price_data = price_map.get(item.symbol)
            if not price_data:
                continue
            signal = spot_svc.analyze_spot_signal(item.symbol, price_data)
            signals_out.append({
                **price_data,
                "signal": signal.get("signal"),
                "reason": signal.get("reason"),
                "target_buy_price": item.target_buy_price,
                "target_sell_price": item.target_sell_price,
            })

        await _safe_send("spot_signals", {"signals": signals_out})

    async def _push_loop() -> None:
        tick = 0
        while True:
            tick += 1
            try:
                coros = []
                if "prices" in channels:
                    coros.append(_push_prices())
                if "trades" in channels and tick % 3 == 0:
                    coros.append(_push_trades())
                if "dashboard" in channels and tick % 6 == 0:
                    coros.append(_push_dashboard())
                if "spot_signals" in channels and tick % 12 == 0:
                    coros.append(_push_spot_signals())
                if "gmx_positions" in channels and tick % 3 == 0:
                    coros.append(_push_gmx_positions())
                if "gtrade_positions" in channels and tick % 3 == 0:
                    coros.append(_push_gtrade_positions())
                if coros:
                    await asyncio.gather(*coros, return_exceptions=True)
            except Exception as exc:
                logger.warning("ws_push_loop_error", user_id=user_id, error=str(exc))
            await asyncio.sleep(TICK_INTERVAL)

    push_task = asyncio.create_task(_push_loop())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")
            if action == "subscribe":
                channels = set(msg.get("channels") or [])
                symbols = [str(s).upper() for s in (msg.get("symbols") or [])]
                await _safe_send("subscribed", {
                    "channels": list(channels),
                    "symbols": symbols,
                })
                logger.info("ws_subscribed", user_id=user_id, channels=list(channels))
            elif action == "ping":
                await _safe_send("pong", {})

    except WebSocketDisconnect:
        logger.info("ws_disconnected", user_id=user_id)
    except Exception as exc:
        logger.warning("ws_error", user_id=user_id, error=str(exc))
    finally:
        push_task.cancel()
        try:
            await push_task
        except asyncio.CancelledError:
            pass
