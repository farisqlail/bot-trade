from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.security import get_current_user_id
from app.models.settings import Settings
from app.schemas.settings import SettingsUpdate, SettingsResponse
from app.config import settings as app_settings

router = APIRouter(prefix="/bot", tags=["bot"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    return s


@router.patch("/settings", response_model=SettingsResponse)
async def update_settings(
    update_data: SettingsUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    for field, value in update_data.model_dump(exclude_none=True).items():
        if field in {"polymarket_api_secret", "polymarket_api_passphrase"} and not value:
            continue
        if field != "polymarket_api_secret" or value:
            setattr(s, field, value)

    await db.flush()
    await db.refresh(s)
    return s


@router.post("/start")
async def start_bot(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")
    if (
        not s.use_public_data_only
        and (
            not s.polymarket_api_key
            or not s.polymarket_api_secret
            or not s.polymarket_api_passphrase
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="Polymarket API key, secret, and passphrase required to start bot",
        )
    s.bot_enabled = True
    await db.flush()
    return {"status": "started", "message": "Bot started successfully"}


@router.post("/test-telegram")
async def test_telegram(
    user_id: int = Depends(get_current_user_id),
):
    from app.services.telegram_service import TelegramService
    tg = TelegramService()
    if not tg.enabled:
        raise HTTPException(
            status_code=400,
            detail="TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset di .env",
        )
    ok = await tg.send_message(
        "✅ <b>Trading Bot Connected!</b>\n\n"
        "Notifikasi Telegram berhasil dikonfigurasi.\n"
        "Bot akan kirim alert saat:\n"
        "• 📊 Scan menemukan sinyal BUY/SELL\n"
        "• 🟢 Trade paper terbuka\n"
        "• ✅/❌ Trade tertutup (SL/TP)"
    )
    if not ok:
        raise HTTPException(status_code=502, detail="Gagal kirim ke Telegram — cek token dan chat_id")
    return {"status": "ok", "message": "Test notification terkirim ke Telegram"}


@router.post("/stop")
async def stop_bot(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if s:
        s.bot_enabled = False
        await db.flush()
    return {"status": "stopped", "message": "Bot stopped successfully"}
