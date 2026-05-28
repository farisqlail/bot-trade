import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.core.security import get_current_user_id
from app.models.settings import Settings
from app.services.gtrade_service import GTradeService, GTRADE_PAIRS
from app.services.exchange_service import ExchangeService
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/gtrade", tags=["gtrade"])


class TradeRequest(BaseModel):
    symbol: str
    direction: str  # "long" or "short"
    collateral_usdc: Optional[float] = None
    leverage: Optional[float] = None
    tp_percent: Optional[float] = None  # 0 or None = no on-chain TP
    sl_percent: Optional[float] = None  # 0 or None = use settings default


class CloseRequest(BaseModel):
    symbol: str


@router.get("/pairs")
async def get_pairs(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ai_service import AIService
    svc = GTradeService()
    active_pairs = await svc.fetch_pairs_from_api()

    exchange = ExchangeService()
    ai_svc = AIService(db)

    async def _fetch_pair_data(sym: str, info: dict) -> dict:
        exchange_sym = sym.replace("/", "")
        try:
            ticker = await exchange.get_ticker(exchange_sym)
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
            analysis = await ai_svc.get_latest_analysis(exchange_sym)
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
        return {
            "symbol": sym,
            "name": info["name"],
            "pair_index": info["index"],
            "max_leverage": info["max_leverage"],
            **price_data,
            "signal": signal,
        }

    pairs = await asyncio.gather(*[
        _fetch_pair_data(sym, info) for sym, info in active_pairs.items()
    ])
    return {"pairs": list(pairs)}


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
        "gtrade_enabled": s.gtrade_enabled,
        "wallet_configured": bool(s.defi_wallet_address and s.defi_wallet_private_key_encrypted),
        "wallet_address": s.defi_wallet_address,
        "leverage": s.gtrade_leverage,
        "collateral_percent": s.gtrade_collateral_percent,
        "open_trades_count": len(s.gtrade_open_trades),
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
    for symbol, pos in s.gtrade_open_trades.items():
        entry_price = float(pos.get("entry_price", 0))
        size_usd = float(pos.get("size_usd", 0))
        collateral = float(pos.get("collateral_usdc", 0))
        is_long = bool(pos.get("is_long", True))
        current_price = None
        pnl_usd = None
        pnl_percent = None
        try:
            ticker = await exchange.get_ticker(symbol.replace("/", ""))
            current_price = ticker["price"]
            if entry_price > 0 and size_usd > 0:
                pct = ((current_price - entry_price) / entry_price
                       if is_long else (entry_price - current_price) / entry_price)
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
            "pair_index": pos.get("pair_index"),
            "trade_index": pos.get("trade_index", 0),
            "tp_price": pos.get("tp_price"),
            "sl_price": pos.get("sl_price"),
            "opened_at": pos.get("opened_at"),
        })
    return {
        "positions": positions,
        "gtrade_enabled": s.gtrade_enabled,
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
    if not s.gtrade_enabled:
        raise HTTPException(status_code=400, detail="gTrade not enabled. Enable in Bot Settings.")
    if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
        raise HTTPException(status_code=400, detail="Wallet not configured.")

    svc = GTradeService()
    await svc.fetch_pairs_from_api()  # warm cache so supports_symbol uses latest list
    symbol = req.symbol.upper()
    if not svc.supports_symbol(symbol):
        raise HTTPException(status_code=400, detail=f"{symbol} not supported by gTrade.")

    is_long = req.direction.lower() == "long"
    try:
        ticker = await ExchangeService().get_ticker(symbol.replace("/", ""))
        current_price = float(ticker["price"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch price: {e}")

    # Fetch real USDC balance from Arbitrum
    from app.services.defi_service import DeFiService
    try:
        balance_info = await DeFiService(network="arbitrum").get_balance(s.defi_wallet_address)
        usdc_balance = float(balance_info["usdc_balance"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch USDC balance: {e}")

    if usdc_balance < 5.0:
        raise HTTPException(
            status_code=400,
            detail=f"USDC balance too low: ${usdc_balance:.2f}. Minimum $5.00 needed. Top up wallet first."
        )

    if req.collateral_usdc:
        collateral = float(req.collateral_usdc)
    else:
        collateral = round(usdc_balance * (s.gtrade_collateral_percent / 100), 2)

    # Ensure collateral ≥ $5 and leaves at least $1 in wallet
    if collateral < 5.0:
        raise HTTPException(status_code=400, detail=f"Collateral ${collateral:.2f} too low (min $5.00). Increase USDC balance or collateral_percent setting.")
    if collateral > usdc_balance - 1.0:
        collateral = round(usdc_balance - 1.0, 2)
        if collateral < 5.0:
            raise HTTPException(status_code=400, detail=f"Not enough USDC. Balance ${usdc_balance:.2f} — need at least $6.00 to trade safely.")

    leverage = req.leverage or s.gtrade_leverage

    # No on-chain TP/SL — user closes manually via closePosition
    tp_price_usd: Optional[float] = None
    sl_price_usd: Optional[float] = None

    logger.info(f"gTrade {symbol} opening {req.direction.upper()} @ {current_price} no on-chain TP/SL")

    try:
        result = await svc.open_position(
            s.defi_wallet_private_key_encrypted,
            symbol,
            is_long=is_long,
            collateral_usdc=collateral,
            leverage=leverage,
            current_price=current_price,
            tp_price_usd=tp_price_usd,
            sl_price_usd=sl_price_usd,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"gTrade open failed: {e}")

    if result.get("status") != "success":
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))

    pair_index = svc.get_pair_index(symbol)
    trade_index = result.get("trade_index", 0)

    open_trades = dict(s.gtrade_open_trades)
    open_trades[symbol] = {
        "is_long": is_long,
        "entry_price": current_price,
        "size_usd": result.get("size_usd", 0.0),
        "collateral_usdc": collateral,
        "pair_index": pair_index,
        "trade_index": trade_index,
        "tp_price": result.get("tp_price"),
        "sl_price": result.get("sl_price"),
        "opened_at": datetime.now(timezone.utc).isoformat(),
    }
    s.gtrade_open_trades = open_trades

    log = list(s.gtrade_activity_log)
    log.insert(0, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "OPENED",
        "symbol": symbol,
        "direction": "LONG" if is_long else "SHORT",
        "entry_price": current_price,
        "size_usd": result.get("size_usd", 0.0),
        "collateral_usdc": collateral,
        "leverage": leverage,
        "tp_price": result.get("tp_price"),
        "sl_price": result.get("sl_price"),
        "tx_hash": result.get("tx_hash"),
        "source": "web",
    })
    s.gtrade_activity_log = log[:50]
    await db.commit()

    return {
        "status": "success",
        "symbol": symbol,
        "direction": "LONG" if is_long else "SHORT",
        "entry_price": current_price,
        "size_usd": result.get("size_usd", 0.0),
        "collateral_usdc": collateral,
        "leverage": leverage,
        "tp_price": result.get("tp_price"),
        "sl_price": result.get("sl_price"),
        "tx_hash": result.get("tx_hash"),
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
    open_trades = dict(s.gtrade_open_trades)
    if symbol not in open_trades:
        raise HTTPException(status_code=404, detail=f"No open trade for {symbol}")

    pos = open_trades[symbol]
    is_long = bool(pos.get("is_long", True))
    size_usd = float(pos.get("size_usd", 0))
    pair_index = int(pos.get("pair_index", 0))
    stored_trade_index = int(pos.get("trade_index", 0))
    entry_price = float(pos.get("entry_price", 0))

    try:
        ticker = await ExchangeService().get_ticker(symbol.replace("/", ""))
        current_price = float(ticker["price"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch price: {e}")

    svc = GTradeService()

    # Always verify trade_index from live API before closing.
    # Stored value may be stale if API was slow at open time.
    trade_index = stored_trade_index
    try:
        live_trades = await svc.get_user_trades(s.defi_wallet_address)
        for t in live_trades:
            pi = t.get("pairIndex") or t.get("pair_index") or t.get("pairindex")
            if pi is not None and int(pi) == pair_index:
                idx = t.get("index") if t.get("index") is not None else (t.get("tradeIndex") or t.get("trade_index") or 0)
                trade_index = int(idx)
                logger.info(f"gTrade close verified trade_index={trade_index} (stored={stored_trade_index}) for {symbol}")
                break
        else:
            logger.warning(f"gTrade close: {symbol} not found in live API, using stored trade_index={stored_trade_index}")
    except Exception as e:
        logger.warning(f"gTrade close live trade_index lookup failed: {e} — using stored={stored_trade_index}")

    try:
        result = await svc.close_position(
            s.defi_wallet_private_key_encrypted,
            pair_index=pair_index,
            trade_index=trade_index,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"gTrade close failed: {e}")

    if result.get("status") != "success":
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))

    pnl_pct = None
    pnl_usd = None
    if entry_price > 0 and size_usd > 0:
        pct = ((current_price - entry_price) / entry_price
               if is_long else (entry_price - current_price) / entry_price)
        pnl_pct = round(pct * 100, 2)
        pnl_usd = round(pct * size_usd, 2)

    del open_trades[symbol]
    s.gtrade_open_trades = open_trades

    log = list(s.gtrade_activity_log)
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
        "tx_hash": result.get("tx_hash"),
        "source": "web",
    })
    s.gtrade_activity_log = log[:50]
    await db.commit()

    return {
        "status": "close_requested",
        "symbol": symbol,
        "direction": "LONG" if is_long else "SHORT",
        "exit_price": current_price,
        "pnl_usd": pnl_usd,
        "pnl_percent": pnl_pct,
        "tx_hash": result.get("tx_hash"),
        "note": "Close request submitted. USDC arrives after gTrade keeper settles (1-5 minutes). Check wallet after.",
    }


class ApplyAiRequest(BaseModel):
    symbol: Optional[str] = None  # None = apply to all open positions


@router.post("/apply-ai-tpsl")
async def apply_ai_tpsl(
    req: ApplyAiRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch AI suggested_tp/sl for open positions and update on-chain via updateTp/updateSl."""
    from app.services.ai_service import AIService
    db_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = db_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
        raise HTTPException(status_code=400, detail="Wallet not configured.")

    ai_svc = AIService(db)
    svc = GTradeService()
    exchange = ExchangeService()

    open_trades = dict(s.gtrade_open_trades)
    symbols_to_update = [req.symbol.upper()] if req.symbol else list(open_trades.keys())

    updated = []
    errors = []

    for symbol in symbols_to_update:
        if symbol not in open_trades:
            continue
        pos = open_trades[symbol]
        pair_index = int(pos.get("pair_index", 0))
        trade_index = int(pos.get("trade_index", 0))
        is_long = bool(pos.get("is_long", True))

        try:
            ticker = await exchange.get_ticker(symbol.replace("/", ""))
            current_price = float(ticker["price"])
        except Exception as e:
            errors.append({"symbol": symbol, "error": f"price fetch: {e}"})
            continue

        try:
            analysis = await ai_svc.get_latest_analysis(symbol.replace("/", ""))
        except Exception:
            analysis = None

        tp_price: Optional[float] = None
        sl_price: Optional[float] = None

        if analysis:
            if analysis.suggested_tp:
                ai_tp = float(analysis.suggested_tp)
                if (is_long and ai_tp > current_price) or (not is_long and ai_tp < current_price):
                    tp_price = ai_tp
            if analysis.suggested_sl:
                ai_sl = float(analysis.suggested_sl)
                if (is_long and ai_sl < current_price) or (not is_long and ai_sl > current_price):
                    sl_price = ai_sl

        # Fall back to settings SL if no AI SL
        if sl_price is None and s.gtrade_sl_percent > 0:
            sl_price = current_price * (1 - s.gtrade_sl_percent / 100) if is_long else current_price * (1 + s.gtrade_sl_percent / 100)

        if not tp_price and not sl_price:
            errors.append({"symbol": symbol, "error": "no AI signal available"})
            continue

        try:
            result = await svc.update_tpsl(
                s.defi_wallet_private_key_encrypted,
                pair_index=pair_index,
                trade_index=trade_index,
                tp_price_usd=tp_price,
                sl_price_usd=sl_price,
            )
            # Persist updated prices to settings
            open_trades[symbol] = {**pos, "tp_price": tp_price, "sl_price": sl_price}
            updated.append({
                "symbol": symbol,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "tp_tx": result.get("tp_tx"),
                "sl_tx": result.get("sl_tx"),
            })
        except Exception as e:
            errors.append({"symbol": symbol, "error": str(e)})

    s.gtrade_open_trades = open_trades

    log = list(s.gtrade_activity_log)
    for u in updated:
        log.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "AI_TPSL",
            "symbol": u["symbol"],
            "tp_price": u["tp_price"],
            "sl_price": u["sl_price"],
            "source": "ai",
        })
    s.gtrade_activity_log = log[:50]
    await db.commit()

    return {"updated": updated, "errors": errors}


@router.post("/force-close-all")
async def force_close_all(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch real open trades from gTrade API and close all with correct indices."""
    db_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = db_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
        raise HTTPException(status_code=400, detail="Wallet not configured.")

    svc = GTradeService()
    try:
        results = await svc.force_close_all(
            s.defi_wallet_private_key_encrypted,
            s.defi_wallet_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Force close failed: {e}")

    # Clear all local position records — actual state is now on-chain
    s.gtrade_open_trades = {}
    log = list(s.gtrade_activity_log)
    for r in results:
        log.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "FORCE_CLOSE",
            "symbol": f"pairIndex:{r.get('pair_index')}",
            "tx_hash": r.get("tx_hash"),
            "source": "force_close_all",
        })
    s.gtrade_activity_log = log[:50]
    await db.commit()

    return {"results": results, "message": "Close requests submitted. gTrade keepers will settle USDC to your wallet within minutes."}


@router.get("/logs")
async def get_logs(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    return {"logs": s.gtrade_activity_log}
