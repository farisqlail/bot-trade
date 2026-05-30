"""
Portfolio consolidated view: paper + Bybit USDT + DeFi USDC + GMX/gTrade collateral.
Each source is fetched with timeout; failures return 0 with an error note.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.database import get_db
from app.models.settings import Settings
from app.models.trade import Trade, TradeStatus
from app.services.exchange_service import ExchangeService
from app.utils.crypto import safe_decrypt as _safe_decrypt
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


async def _safe(coro, default=0.0):
    try:
        return await asyncio.wait_for(coro, timeout=8.0)
    except Exception:
        return default


@router.get("")
async def get_portfolio(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    exchange = ExchangeService()
    sources = {}
    errors = []

    # ── Paper balance ─────────────────────────────────────────────────────────
    paper_balance = s.paper_balance

    # Paper open trades unrealized PnL (live prices)
    open_result = await db.execute(
        select(Trade).where(and_(Trade.user_id == user_id, Trade.status == TradeStatus.OPEN))
    )
    open_trades = open_result.scalars().all()
    paper_unrealized = 0.0
    for t in open_trades:
        if t.notes and "paper" in t.notes:
            try:
                ticker = await _safe(exchange.get_ticker(t.symbol))
                if isinstance(ticker, dict) and ticker.get("price"):
                    price = ticker["price"]
                    if t.direction.value == "LONG":
                        paper_unrealized += (price - t.entry_price) * t.quantity
                    else:
                        paper_unrealized += (t.entry_price - price) * t.quantity
            except Exception:
                pass

    sources["paper"] = {
        "label": "Paper Trading",
        "balance": round(paper_balance, 2),
        "unrealized_pnl": round(paper_unrealized, 2),
        "total": round(paper_balance + paper_unrealized, 2),
        "currency": "USD (simulated)",
    }

    # ── Bybit USDT ────────────────────────────────────────────────────────────
    bybit_usdt = 0.0
    if s.polymarket_api_key and s.polymarket_api_secret:
        try:
            from app.services.bybit_order_service import BybitOrderService
            api_key = _safe_decrypt(s.polymarket_api_key)
            api_secret = _safe_decrypt(s.polymarket_api_secret)
            if api_key and api_secret:
                order_svc = BybitOrderService(api_key=api_key, api_secret=api_secret)
                bybit_usdt = await _safe(order_svc.get_wallet_balance("USDT"))
        except Exception as exc:
            errors.append(f"Bybit: {exc}")

    sources["bybit"] = {
        "label": "Bybit USDT",
        "balance": round(bybit_usdt, 2),
        "unrealized_pnl": 0.0,
        "total": round(bybit_usdt, 2),
        "currency": "USDT",
    }

    # ── DeFi USDC (all configured networks) ───────────────────────────────────
    defi_usdc = 0.0
    defi_held_symbols: list = []
    if s.defi_wallet_address:
        from app.services.defi_service import DeFiService
        for network in s.defi_networks:
            try:
                svc = DeFiService(network=network)
                info = await _safe(svc.get_balance(s.defi_wallet_address), {})
                defi_usdc += float(info.get("usdc_balance", 0))
            except Exception as exc:
                errors.append(f"DeFi {network}: {exc}")

        # Held token count (entry_prices tracks which symbols are held, not qty)
        defi_held_symbols = list((s.defi_entry_prices or {}).keys())

    sources["defi"] = {
        "label": "DeFi Wallet (USDC)",
        "balance": round(defi_usdc, 2),
        "held_tokens": defi_held_symbols,
        "held_tokens_count": len(defi_held_symbols),
        "total": round(defi_usdc, 2),
        "currency": "USDC",
        "wallet": s.defi_wallet_address,
    }

    # ── GMX collateral ────────────────────────────────────────────────────────
    gmx_collateral = sum(
        float(pos.get("collateral_usdc", 0))
        for pos in (s.gmx_open_positions or {}).values()
    )
    gmx_unrealized = 0.0
    for symbol, pos in (s.gmx_open_positions or {}).items():
        entry_price = float(pos.get("entry_price", 0))
        size_usd = float(pos.get("size_usd", 0))
        is_long = bool(pos.get("is_long", True))
        if not entry_price or not size_usd:
            continue
        try:
            ticker = await _safe(exchange.get_ticker(symbol))
            if isinstance(ticker, dict) and ticker.get("price"):
                price = ticker["price"]
                pct = (price - entry_price) / entry_price if is_long else (entry_price - price) / entry_price
                gmx_unrealized += pct * size_usd
        except Exception:
            pass

    sources["gmx"] = {
        "label": "GMX Collateral",
        "balance": round(gmx_collateral, 2),
        "unrealized_pnl": round(gmx_unrealized, 2),
        "total": round(gmx_collateral + gmx_unrealized, 2),
        "currency": "USDC",
        "positions": len(s.gmx_open_positions or {}),
    }

    # ── gTrade collateral ─────────────────────────────────────────────────────
    gtrade_collateral = sum(
        float(pos.get("collateral_usdc", 0))
        for pos in (s.gtrade_open_trades or {}).values()
    )
    gtrade_unrealized = 0.0
    for symbol, pos in (s.gtrade_open_trades or {}).items():
        entry_price = float(pos.get("entry_price", 0))
        size_usd = float(pos.get("size_usd", 0))
        is_long = bool(pos.get("is_long", True))
        if not entry_price or not size_usd:
            continue
        try:
            ticker_sym = symbol.replace("/", "")
            ticker = await _safe(exchange.get_ticker(ticker_sym))
            if isinstance(ticker, dict) and ticker.get("price"):
                price = ticker["price"]
                pct = (price - entry_price) / entry_price if is_long else (entry_price - price) / entry_price
                gtrade_unrealized += pct * size_usd
        except Exception:
            pass

    sources["gtrade"] = {
        "label": "gTrade Collateral",
        "balance": round(gtrade_collateral, 2),
        "unrealized_pnl": round(gtrade_unrealized, 2),
        "total": round(gtrade_collateral + gtrade_unrealized, 2),
        "currency": "USDC",
        "positions": len(s.gtrade_open_trades or {}),
    }

    total = sum(src["total"] for src in sources.values())

    return {
        "total_portfolio_value": round(total, 2),
        "sources": sources,
        "errors": errors,
    }
