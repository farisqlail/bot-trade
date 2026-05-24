from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List
from app.database import get_db
from app.core.security import get_current_user_id
from app.services.ai_service import AIService
from app.services.scanner_service import ScannerService
from app.services.exchange_service import ExchangeService
from app.models.ai_analysis import AIAnalysis
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/ai", tags=["ai-analysis"])


class AIAnalysisResponse(BaseModel):
    id: int
    symbol: str
    model_name: str
    trend: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    analysis_text: str
    recommended_action: Optional[str] = None
    suggested_entry: Optional[float] = None
    suggested_sl: Optional[float] = None
    suggested_tp: Optional[float] = None
    price_at_analysis: Optional[float] = None
    processing_time_ms: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OpportunityResponse(BaseModel):
    symbol: str
    score: float
    trend: str
    sentiment: str
    confidence: float
    recommended_action: str
    suggested_entry: float
    suggested_sl: float
    suggested_tp: float
    price_at_analysis: float
    change_24h: float
    volume_24h: float
    polymarket_bias_score: float
    polymarket_market_count: int
    analysis_text: str
    analysis_id: Optional[int] = None
    created_at: Optional[str] = None
    paper_trade_id: Optional[int] = None


@router.post("/analyze/{symbol}", response_model=AIAnalysisResponse)
async def trigger_analysis(
    symbol: str,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    exchange_svc = ExchangeService()
    try:
        market_data = await exchange_svc.get_market_data(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Exchange error: {str(e)}")

    ai_svc = AIService(db)
    try:
        analysis = await ai_svc.analyze_market(symbol.upper(), market_data)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI service error: {str(e)}")

    return analysis


@router.get("/latest/{symbol}", response_model=AIAnalysisResponse)
async def get_latest_analysis(
    symbol: str,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    ai_svc = AIService(db)
    analysis = await ai_svc.get_latest_analysis(symbol.upper())
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this symbol")
    return analysis


@router.get("/history/{symbol}", response_model=List[AIAnalysisResponse])
async def get_analysis_history(
    symbol: str,
    limit: int = Query(20, le=100),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    ai_svc = AIService(db)
    return await ai_svc.get_analysis_history(symbol.upper(), limit)


@router.get("/opportunities/cached", response_model=List[OpportunityResponse])
async def get_cached_opportunities(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    subq = (
        select(AIAnalysis.symbol, func.max(AIAnalysis.created_at).label("max_ts"))
        .group_by(AIAnalysis.symbol)
        .subquery()
    )
    result = await db.execute(
        select(AIAnalysis)
        .join(
            subq,
            (AIAnalysis.symbol == subq.c.symbol) & (AIAnalysis.created_at == subq.c.max_ts),
        )
        .order_by(desc(AIAnalysis.created_at))
    )
    analyses = result.scalars().all()
    return [
        {
            "symbol": a.symbol,
            "score": 0.0,
            "trend": a.trend or "SIDEWAYS",
            "sentiment": a.sentiment or "HOLD",
            "confidence": a.confidence or 0.0,
            "recommended_action": a.recommended_action or "HOLD",
            "suggested_entry": a.suggested_entry or 0.0,
            "suggested_sl": a.suggested_sl or 0.0,
            "suggested_tp": a.suggested_tp or 0.0,
            "price_at_analysis": a.price_at_analysis or 0.0,
            "change_24h": float((a.market_data_snapshot or {}).get("change_24h", 0)),
            "volume_24h": float((a.market_data_snapshot or {}).get("volume_24h", 0)),
            "polymarket_bias_score": float((a.market_data_snapshot or {}).get("polymarket_bias_score", 0)),
            "polymarket_market_count": int((a.market_data_snapshot or {}).get("polymarket_market_count", 0)),
            "analysis_text": a.analysis_text,
            "analysis_id": a.id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in analyses
    ]


async def _scan_opportunities_impl(
    deep_analysis: bool = Query(True),
    execute_paper: bool = Query(False),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    scanner = ScannerService(db)
    try:
        return await scanner.scan_opportunities(
            user_id=user_id,
            deep_analysis=deep_analysis,
            execute_paper=execute_paper,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Scanner error: {str(e)}")


@router.get("/opportunities", response_model=List[OpportunityResponse])
async def get_opportunities(
    deep_analysis: bool = Query(True),
    execute_paper: bool = Query(False),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await _scan_opportunities_impl(
        deep_analysis=deep_analysis,
        execute_paper=execute_paper,
        user_id=user_id,
        db=db,
    )


@router.post("/opportunities", response_model=List[OpportunityResponse])
async def scan_opportunities(
    deep_analysis: bool = Query(True),
    execute_paper: bool = Query(False),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await _scan_opportunities_impl(
        deep_analysis=deep_analysis,
        execute_paper=execute_paper,
        user_id=user_id,
        db=db,
    )
