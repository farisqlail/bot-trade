from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List
from app.database import get_db
from app.core.security import get_current_user_id
from app.services.risk_service import RiskService
from app.services.exchange_service import ExchangeService
from app.models.risk_event import RiskEvent
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskEventResponse(BaseModel):
    id: int
    user_id: int
    event_type: str
    severity: str
    title: str
    description: Optional[str] = None
    triggered_value: Optional[float] = None
    threshold_value: Optional[float] = None
    action_taken: Optional[str] = None
    is_resolved: int
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/status")
async def get_risk_status(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    exchange_svc = ExchangeService()
    account = await exchange_svc.get_account_balance()
    risk_svc = RiskService(db)
    return await risk_svc.get_risk_status(user_id, account["balance"])


@router.get("/events", response_model=List[RiskEventResponse])
async def get_risk_events(
    limit: int = Query(50, le=200),
    unresolved_only: bool = False,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    filters = [RiskEvent.user_id == user_id]
    if unresolved_only:
        filters.append(RiskEvent.is_resolved == 0)

    result = await db.execute(
        select(RiskEvent).where(and_(*filters))
        .order_by(desc(RiskEvent.created_at))
        .limit(limit)
    )
    return result.scalars().all()
