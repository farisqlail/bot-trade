from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.core.security import get_current_user_id
from app.models.settings import Settings
from app.services.gmx_service import GMXService, GMX_MARKETS
from app.services.exchange_service import ExchangeService
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/gmx", tags=["gmx"])


class TradeRequest(BaseModel):
    symbol: str
    direction: str  # "long" or "short"
    collateral_usdc: Optional[float] = None
    leverage: Optional[float] = None


class CloseRequest(BaseModel):
    symbol: str


@router.get("/markets")
async def get_markets(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ai_service import AIService
    exchange = ExchangeService()
    ai_svc = AIService(db)
    markets = []
    for sym in GMX_MARKETS:
        try:
            ticker = await exchange.get_ticker(sym)
            price_data = {
                "price": ticker["price"],
                "change_24h": ticker["change_24h"],
                "high_24h": ticker["high_24h"],
                "low_24h": ticker["low_24h"],
                "volume_24h": ticker["volume_24h"],
            }
        except Exception:
            price_data = {"price": None, "change_24h": None,
                          "high_24h": None, "low_24h": None, "volume_24h": None}
        try:
            analysis = await ai_svc.get_latest_analysis(sym)
            signal = {
                "action": analysis.recommended_action if analysis else None,
                "sentiment": analysis.sentiment if analysis else None,
                "confidence": analysis.confidence if analysis else None,
                "suggested_tp": analysis.suggested_tp if analysis else None,
                "suggested_sl": analysis.suggested_sl if analysis else None,
            }
        except Exception:
            signal = {"action": None, "sentiment": None, "confidence": None,
                      "suggested_tp": None, "suggested_sl": None}
        markets.append({"symbol": sym, **price_data, "signal": signal})
    return {"markets": markets}


@router.get("/status")
async def get_status(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    return {
        "gmx_enabled": s.gmx_enabled,
        "wallet_configured": bool(s.defi_wallet_address and s.defi_wallet_private_key_encrypted),
        "leverage": s.gmx_leverage,
        "collateral_percent": s.gmx_collateral_percent,
        "open_positions_count": len(s.gmx_open_positions),
    }


@router.get("/positions")
async def get_positions(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    exchange = ExchangeService()
    positions = []
    for symbol, pos in s.gmx_open_positions.items():
        entry_price = float(pos.get("entry_price", 0))
        size_usd = float(pos.get("size_usd", 0))
        collateral = float(pos.get("collateral_usdc", 0))
        is_long = bool(pos.get("is_long", True))
        current_price = None
        pnl_usd = None
        pnl_percent = None
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
    return {
        "positions": positions,
        "gmx_enabled": s.gmx_enabled,
        "wallet_address": s.defi_wallet_address,
    }


@router.post("/trade")
async def open_trade(
    req: TradeRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    db_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = db_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    if not s.gmx_enabled:
        raise HTTPException(status_code=400, detail="GMX trading not enabled. Enable in Bot Settings.")
    if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
        raise HTTPException(status_code=400, detail="Wallet not configured.")

    svc = GMXService()
    symbol = req.symbol.upper()
    if not svc.supports_symbol(symbol):
        raise HTTPException(status_code=400, detail=f"{symbol} not supported by GMX.")

    is_long = req.direction.lower() == "long"
    try:
        ticker = await ExchangeService().get_ticker(symbol)
        current_price = float(ticker["price"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch price: {e}")

    if req.collateral_usdc:
        collateral = float(req.collateral_usdc)
    else:
        from app.services.defi_service import DeFiService
        balance_info = await DeFiService(network="arbitrum").get_balance(s.defi_wallet_address)
        usdc = balance_info["usdc_balance"]
        collateral = round(usdc * (s.gmx_collateral_percent / 100), 2)

    if collateral < 1.0:
        raise HTTPException(status_code=400, detail=f"Collateral too low: ${collateral:.2f}")

    leverage = req.leverage or s.gmx_leverage
    try:
        trade_result = await svc.open_position(
            s.defi_wallet_private_key_encrypted,
            symbol,
            is_long=is_long,
            collateral_usdc=collateral,
            leverage=leverage,
            current_price=current_price,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GMX trade failed: {e}")

    if trade_result.get("status") != "success":
        raise HTTPException(status_code=502, detail=trade_result.get("error", "Unknown error"))

    open_positions = dict(s.gmx_open_positions)
    open_positions[symbol] = {
        "is_long": is_long,
        "entry_price": current_price,
        "size_usd": trade_result.get("size_usd", 0.0),
        "collateral_usdc": collateral,
        "opened_at": datetime.now(timezone.utc).isoformat(),
    }
    s.gmx_open_positions = open_positions

    log = list(s.gmx_activity_log)
    log.insert(0, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "OPENED",
        "symbol": symbol,
        "direction": "LONG" if is_long else "SHORT",
        "entry_price": current_price,
        "size_usd": trade_result.get("size_usd", 0.0),
        "collateral_usdc": collateral,
        "tx_hash": trade_result.get("tx_hash"),
        "source": "web",
    })
    s.gmx_activity_log = log[:50]
    await db.commit()

    return {
        "status": "success",
        "symbol": symbol,
        "direction": "LONG" if is_long else "SHORT",
        "entry_price": current_price,
        "size_usd": trade_result.get("size_usd", 0.0),
        "collateral_usdc": collateral,
        "leverage": leverage,
        "tx_hash": trade_result.get("tx_hash"),
    }


@router.post("/close")
async def close_position(
    req: CloseRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    db_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = db_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
        raise HTTPException(status_code=400, detail="Wallet not configured.")

    symbol = req.symbol.upper()
    open_positions = dict(s.gmx_open_positions)
    if symbol not in open_positions:
        raise HTTPException(status_code=404, detail=f"No open position for {symbol}")

    pos = open_positions[symbol]
    is_long = bool(pos.get("is_long", True))
    size_usd = float(pos.get("size_usd", 0))

    try:
        ticker = await ExchangeService().get_ticker(symbol)
        current_price = float(ticker["price"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch price: {e}")

    svc = GMXService()
    try:
        close_result = await svc.close_position(
            s.defi_wallet_private_key_encrypted,
            symbol,
            is_long=is_long,
            size_usd=size_usd,
            current_price=current_price,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GMX close failed: {e}")

    if close_result.get("status") != "success":
        raise HTTPException(status_code=502, detail=close_result.get("error", "Unknown error"))

    # Calculate realized PnL for log
    entry_price = float(pos.get("entry_price", 0))
    pnl_pct = None
    pnl_usd = None
    if entry_price > 0 and size_usd > 0:
        pct = (current_price - entry_price) / entry_price if is_long else (entry_price - current_price) / entry_price
        pnl_pct = round(pct * 100, 2)
        pnl_usd = round(pct * size_usd, 2)

    del open_positions[symbol]
    s.gmx_open_positions = open_positions

    log = list(s.gmx_activity_log)
    log.insert(0, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "CLOSED",
        "symbol": symbol,
        "direction": "LONG" if is_long else "SHORT",
        "exit_price": current_price,
        "entry_price": entry_price,
        "size_usd": size_usd,
        "pnl_usd": pnl_usd,
        "pnl_percent": pnl_pct,
        "tx_hash": close_result.get("tx_hash"),
        "source": "web",
    })
    s.gmx_activity_log = log[:50]
    await db.commit()

    return {
        "status": "success",
        "symbol": symbol,
        "direction": "LONG" if is_long else "SHORT",
        "exit_price": current_price,
        "pnl_usd": pnl_usd,
        "pnl_percent": pnl_pct,
        "tx_hash": close_result.get("tx_hash"),
    }


@router.get("/logs")
async def get_logs(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    return {"logs": s.gmx_activity_log}
