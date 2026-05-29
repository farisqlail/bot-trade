from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import math

from app.config import settings as app_settings
from app.database import get_db
from app.core.security import get_current_user_id
from app.models.settings import Settings
from app.services.bybit_order_service import BybitOrderService
from app.services.exchange_service import ExchangeService
from app.core.logging_config import get_logger
from app.utils.crypto import safe_decrypt as _safe_decrypt

logger = get_logger(__name__)
router = APIRouter(prefix="/bybit-futures", tags=["bybit-futures"])


class BybitFuturesTradeRequest(BaseModel):
    symbol: str
    direction: str          # "long" or "short"
    leverage: Optional[int] = None  # None = use settings.bybit_leverage
    usdt_amount: Optional[float] = None
    sl_percent: Optional[float] = None
    tp_percent: Optional[float] = None


def _round_qty(qty_raw: float, price: float) -> str:
    """Round qty to a sensible step based on price magnitude."""
    if price >= 1000:
        qty = round(qty_raw, 3)
    elif price >= 10:
        qty = round(qty_raw, 2)
    elif price >= 0.1:
        qty = round(qty_raw, 1)
    else:
        # Very low price coins (PEPE, SHIB etc.) — whole numbers
        qty = max(1, int(math.floor(qty_raw)))
    return str(qty) if qty > 0 else "0"


@router.post("/trade")
async def open_bybit_futures_trade(
    req: BybitFuturesTradeRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    db_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = db_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    api_key = _safe_decrypt(s.polymarket_api_key) or app_settings.BYBIT_API_KEY
    api_secret = _safe_decrypt(s.polymarket_api_secret) or app_settings.BYBIT_API_SECRET
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="Bybit API keys not configured. Set in Bot Settings → Bybit Futures API.")
    key_source = "db" if s.polymarket_api_key else "env"
    logger.info(f"bybit_futures using key_source={key_source} key={api_key[:4]}...{api_key[-4:]} base_url={app_settings.BYBIT_BASE_URL}")

    symbol = req.symbol.upper()
    if not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    exchange = ExchangeService()
    try:
        ticker = await exchange.get_ticker(symbol)
        current_price = float(ticker["price"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch price for {symbol}: {e}")

    svc = BybitOrderService(api_key=api_key, api_secret=api_secret)

    leverage = max(1, min(req.leverage if req.leverage is not None else s.bybit_leverage, 100))
    try:
        await svc.set_leverage(symbol, leverage)
    except Exception as e:
        logger.warning(f"bybit_set_leverage_failed symbol={symbol} err={e}")

    usdt_amount = req.usdt_amount
    if not usdt_amount or usdt_amount <= 0:
        try:
            balance_usdt = await svc.get_wallet_balance("USDT")
            balance_usdc = await svc.get_wallet_balance("USDC")
            balance = max(balance_usdt, balance_usdc)
            used_coin = "USDT" if balance_usdt >= balance_usdc else "USDC"
            logger.info(f"bybit_balance USDT={balance_usdt} USDC={balance_usdc} using={used_coin} balance={balance}")
            usdt_amount = round(balance * s.bybit_collateral_percent / 100, 2)
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "API key" in err_str.lower() or "invalid" in err_str.lower():
                raise HTTPException(
                    status_code=400,
                    detail="Bybit API key invalid. Masuk Bot Settings → Bybit Futures API → isi API Key & Secret yang benar dari Bybit.com."
                )
            raise HTTPException(status_code=502, detail=f"Cannot fetch wallet balance: {e}")

    if usdt_amount < 1.0:
        raise HTTPException(status_code=400, detail=f"USDT amount too low: ${usdt_amount:.2f} (min $1.00)")

    notional = usdt_amount * leverage
    qty_str = _round_qty(notional / current_price, current_price)
    if qty_str == "0" or float(qty_str) <= 0:
        raise HTTPException(status_code=400, detail="Calculated qty is zero. Increase amount or reduce leverage.")

    is_long = req.direction.lower() == "long"
    side = "Buy" if is_long else "Sell"

    effective_sl = req.sl_percent if req.sl_percent is not None else s.bybit_sl_percent
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    if effective_sl and effective_sl > 0:
        sl_price = current_price * (1 - effective_sl / 100) if is_long else current_price * (1 + effective_sl / 100)
    if req.tp_percent and req.tp_percent > 0:
        tp_price = current_price * (1 + req.tp_percent / 100) if is_long else current_price * (1 - req.tp_percent / 100)

    try:
        result = await svc.place_order(
            symbol=symbol,
            side=side,
            qty=qty_str,
            order_type="Market",
            stop_loss=sl_price,
            take_profit=tp_price,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Bybit order failed: {e}")

    logger.info(f"bybit_futures_opened symbol={symbol} dir={req.direction.upper()} qty={qty_str} lev={leverage}x price={current_price} sl={effective_sl}%")

    return {
        "status": "success",
        "symbol": symbol,
        "direction": req.direction.upper(),
        "entry_price": current_price,
        "qty": float(qty_str),
        "leverage": leverage,
        "usdt_amount": usdt_amount,
        "sl_price": sl_price,
        "sl_percent": effective_sl,
        "tp_price": tp_price,
        "order_id": result.get("orderId"),
    }


@router.get("/balance")
async def get_bybit_balance(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    db_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = db_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    api_key = _safe_decrypt(s.polymarket_api_key) or app_settings.BYBIT_API_KEY
    api_secret = _safe_decrypt(s.polymarket_api_secret) or app_settings.BYBIT_API_SECRET
    if not api_key or not api_secret:
        return {"usdt": 0.0, "usdc": 0.0, "total": 0.0, "configured": False}

    svc = BybitOrderService(api_key=api_key, api_secret=api_secret)
    try:
        usdt = await svc.get_wallet_balance("USDT")
        usdc = await svc.get_wallet_balance("USDC")
        return {"usdt": usdt, "usdc": usdc, "total": round(usdt + usdc, 4), "configured": True}
    except Exception as e:
        return {"usdt": 0.0, "usdc": 0.0, "total": 0.0, "configured": True, "error": str(e)}


@router.get("/deposit-address")
async def get_deposit_address(
    coin: str = "USDC",
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    db_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = db_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    api_key = _safe_decrypt(s.polymarket_api_key) or app_settings.BYBIT_API_KEY
    api_secret = _safe_decrypt(s.polymarket_api_secret) or app_settings.BYBIT_API_SECRET
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="Bybit API keys not configured.")

    svc = BybitOrderService(api_key=api_key, api_secret=api_secret)
    try:
        result = await svc.get_deposit_address(coin=coin, chain="ARB")
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot get deposit address: {e}. Ensure API key has Transfers permission.")
