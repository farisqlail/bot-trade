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

    service = DeFiService(network=s.defi_network or "arbitrum")
    token_address = service.get_token_address(req.symbol)
    if not token_address:
        raise HTTPException(status_code=400, detail=f"Symbol {req.symbol} not supported for DeFi")

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
            )
        elif req.direction == "sell":
            return await service.sell_all_to_usdc(
                s.defi_wallet_private_key_encrypted,
                token_address,
                slippage=s.defi_slippage / 100,
            )
        else:
            raise HTTPException(status_code=400, detail="direction must be 'buy' or 'sell'")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("defi_swap_error", error=str(e), symbol=req.symbol, direction=req.direction)
        raise HTTPException(status_code=502, detail=f"Swap failed: {str(e)}")
