from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.core.security import get_current_user_id
from app.services.tuning_service import TuningService
from app.services.telegram_service import TelegramService
from app.models.tuning import TuningHistory

router = APIRouter(prefix="/tuning", tags=["tuning"])


class TuningHistoryResponse(BaseModel):
    id: int
    user_id: int
    status: str
    old_risk_percent: float
    new_risk_percent: float
    change_direction: Optional[str] = None
    reason: Optional[str] = None
    metrics_snapshot: Optional[dict] = None
    telegram_message_id: Optional[int] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


@router.get("/history", response_model=list[TuningHistoryResponse])
async def get_tuning_history(
    limit: int = 20,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    svc = TuningService(db)
    return await svc.get_history(user_id, limit=min(limit, 100))


@router.get("/pending", response_model=Optional[TuningHistoryResponse])
async def get_pending_tuning(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    svc = TuningService(db)
    return await svc.get_pending(user_id)


@router.post("/{tuning_id}/approve", response_model=TuningHistoryResponse)
async def approve_tuning(
    tuning_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    svc = TuningService(db)
    try:
        record = await svc.approve(tuning_id, user_id)
        await db.commit()
        tg = TelegramService()
        if record.telegram_message_id:
            await tg.edit_message_text(
                record.telegram_message_id,
                f"✅ <b>Tuning Approved (via dashboard)</b>\n"
                f"Risk: <code>{record.old_risk_percent:.2f}%</code> → <code>{record.new_risk_percent:.2f}%</code>",
            )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{tuning_id}/reject", response_model=TuningHistoryResponse)
async def reject_tuning(
    tuning_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    svc = TuningService(db)
    try:
        record = await svc.reject(tuning_id, user_id)
        await db.commit()
        tg = TelegramService()
        if record.telegram_message_id:
            await tg.edit_message_text(
                record.telegram_message_id,
                f"❌ <b>Tuning Rejected (via dashboard)</b>\n"
                f"Risk remains at <code>{record.old_risk_percent:.2f}%</code>.",
            )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run", response_model=Optional[TuningHistoryResponse])
async def run_manual_tuning(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger tuning analysis (bypasses frequency check for one-off run)."""
    from app.models.settings import Settings
    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Settings not found")

    svc = TuningService(db)
    record = await svc.run_tuning(user_id)

    if record and record.status == "pending":
        tg = TelegramService()
        msg_id = await tg.notify_tuning_recommendation(
            tuning_id=record.id,
            approval_token=record.approval_token,
            old_risk=record.old_risk_percent,
            new_risk=record.new_risk_percent,
            direction=record.change_direction or "no_change",
            reason=record.reason or "",
            metrics=record.metrics_snapshot or {},
        )
        if msg_id:
            record.telegram_message_id = msg_id

    await db.commit()
    return record
