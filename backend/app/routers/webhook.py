from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging_config import get_logger
from app.database import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if settings.TELEGRAM_WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != settings.TELEGRAM_WEBHOOK_SECRET:
            logger.warning("telegram_webhook_invalid_secret", ip=request.client.host if request.client else "unknown")
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    else:
        logger.warning("telegram_webhook_no_secret_configured_open_endpoint")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logger.info("telegram_webhook_received", update_id=body.get("update_id"))

    from app.services.telegram_callback_service import process_update
    try:
        await process_update(body, db)
    except Exception as exc:
        logger.error("telegram_webhook_process_error", error=str(exc), update_id=body.get("update_id"))

    # Always return 200 — prevents Telegram from retrying failed updates
    return Response(status_code=200)
