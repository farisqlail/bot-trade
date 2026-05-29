from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.core.security import get_current_user_id
from app.models.settings import Settings
from app.services.defi_service import DeFiService, NETWORKS
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/defi", tags=["defi"])


class TestConnectionRequest(BaseModel):
    wallet_address: str
    network: str = "arbitrum"


class SwapRequest(BaseModel):
    symbol: str  # e.g. "ETHUSDT"
    direction: str  # "buy" or "sell"
    amount_usdc: Optional[float] = None  # required for buy; sell uses full balance


@router.get("/networks")
async def get_supported_networks():
    return {
        name: {"chain_id": cfg["chain_id"], "rpc": cfg["rpc"]}
        for name, cfg in NETWORKS.items()
    }


@router.post("/test-connection")
async def test_connection(req: TestConnectionRequest):
    try:
        service = DeFiService(network=req.network)
        return await service.get_balance(req.wallet_address)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")


@router.get("/balance")
async def get_wallet_balance(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s or not s.defi_wallet_address:
        raise HTTPException(status_code=400, detail="No wallet address configured")

    try:
        service = DeFiService(network=s.defi_network or "arbitrum")
        return await service.get_balance(s.defi_wallet_address)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Wallet balance fetch failed: {str(e)}")


@router.get("/config")
async def get_defi_config(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return current DeFi settings (no private key). Use to verify configured network."""
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    configured_network = s.defi_network or "arbitrum"
    balances = {}
    if s.defi_wallet_address:
        for net in ["arbitrum", "base", "optimism", "polygon"]:
            try:
                b = await DeFiService(network=net).get_balance(s.defi_wallet_address)
                balances[net] = {"eth": b["eth_balance"], "usdc": b["usdc_balance"]}
            except Exception:
                balances[net] = {"eth": None, "usdc": None}
    return {
        "configured_network": configured_network,
        "defi_enabled": s.defi_enabled,
        "wallet_address": s.defi_wallet_address,
        "has_private_key": s.defi_has_private_key,
        "balances": balances,
    }


@router.get("/check/{symbol}")
async def check_token_support(
    symbol: str,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    network = (s.defi_network if s else None) or "arbitrum"
    svc = DeFiService(network=network)
    meta = await svc.get_token_metadata(symbol.upper())
    if not meta:
        return {"supported": False, "symbol": symbol.upper(), "network": None, "address": None}
    return {
        "supported": True,
        "symbol": symbol.upper(),
        "network": meta.get("network", network),
        "address": meta["address"],
    }


@router.post("/swap")
async def execute_swap(
    req: SwapRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    if not s.defi_enabled:
        raise HTTPException(status_code=400, detail="DeFi trading not enabled")
    if not s.defi_wallet_address or not s.defi_wallet_private_key_encrypted:
        raise HTTPException(status_code=400, detail="Wallet not configured")

    configured_network = s.defi_network or "arbitrum"
    discovery_svc = DeFiService(network=configured_network)
    # strict_network=True: only swap on user's configured network, never silently route to another chain
    token_meta = await discovery_svc.get_token_metadata(req.symbol, strict_network=True)
    if not token_meta:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol {req.symbol} has no DEX pool on {configured_network}. "
                   f"Change your DeFi network in settings or use a token available on {configured_network}."
        )

    token_address = token_meta["address"]
    service = DeFiService(network=configured_network)

    # Pre-flight: verify user has gas on configured network before attempting swap
    try:
        bal = await service.get_balance(s.defi_wallet_address)
        if bal["eth_balance"] < 0.0001:
            gas_token = "BNB" if configured_network == "bsc" else "MATIC" if configured_network == "polygon" else "ETH"
            hint = ""
            if configured_network != "arbitrum":
                try:
                    arb_bal = await DeFiService(network="arbitrum").get_balance(s.defi_wallet_address)
                    if arb_bal["eth_balance"] >= 0.0001:
                        hint = f" Your wallet has {arb_bal['eth_balance']:.6f} ETH on Arbitrum — change DeFi network to Arbitrum in Settings."
                except Exception:
                    pass
            raise HTTPException(
                status_code=400,
                detail=f"No gas on {configured_network}: wallet has {bal['eth_balance']:.6f} {gas_token}.{hint}"
            )
    except HTTPException:
        raise
    except Exception as pre_err:
        # Base/polygon RPC failed — still check Arbitrum to guide user
        if configured_network != "arbitrum":
            try:
                arb_bal = await DeFiService(network="arbitrum").get_balance(s.defi_wallet_address)
                if arb_bal["eth_balance"] >= 0.0001:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Cannot reach {configured_network} RPC ({pre_err}). "
                            f"Your wallet has {arb_bal['eth_balance']:.6f} ETH on Arbitrum — "
                            f"go to BotSettings → DeFi → change Network to Arbitrum One → Save."
                        ),
                    )
            except HTTPException:
                raise
            except Exception:
                pass

    try:
        if req.direction == "buy":
            if not req.amount_usdc:
                balance = await service.get_balance(s.defi_wallet_address)
                req.amount_usdc = round(balance["usdc_balance"] * (s.defi_trade_percent / 100), 2)
            if req.amount_usdc < 0.01:
                raise HTTPException(status_code=400, detail="USDC balance too low")
            return await service.swap_usdc_to_token(
                s.defi_wallet_private_key_encrypted,
                token_address,
                req.amount_usdc,
                slippage=s.defi_slippage / 100,
                wallet_address=s.defi_wallet_address,
            )
        elif req.direction == "sell":
            return await service.sell_all_to_usdc(
                s.defi_wallet_private_key_encrypted,
                token_address,
                slippage=s.defi_slippage / 100,
                wallet_address=s.defi_wallet_address,
            )
        else:
            raise HTTPException(status_code=400, detail="direction must be 'buy' or 'sell'")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("defi_swap_error", error=str(e), symbol=req.symbol, direction=req.direction)
        raise HTTPException(status_code=502, detail=f"Swap failed: {str(e)}")
