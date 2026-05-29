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
from app.models.settings import Settings
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


class WatchRequest(BaseModel):
    symbol: str
    execute_defi: bool = True


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
    model_name: Optional[str] = None
    analysis_id: Optional[int] = None
    created_at: Optional[str] = None
    paper_trade_id: Optional[int] = None


@router.post("/watch", response_model=List[OpportunityResponse])
async def watch_and_scan(
    request: WatchRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    symbol = request.symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    result = await db.execute(select(Settings).where(Settings.user_id == user_id))
    settings_obj = result.scalar_one_or_none()
    if settings_obj:
        current = list(settings_obj.scanner_watchlist)
        if symbol not in current:
            current.append(symbol)
            settings_obj.scanner_watchlist = current
            await db.commit()

    scanner = ScannerService(db)
    try:
        return await scanner.scan_specific_symbols(
            user_id=user_id,
            symbols=[symbol],
            deep_analysis=True,
            execute_defi=request.execute_defi,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Scan error: {str(e)}")


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
            "model_name": a.model_name,
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


_LARGE_CAPS = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT", "MATICUSDT",
    "TRXUSDT", "LINKUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT",
}


@router.get("/altcoins")
async def scan_altcoins(
    limit: int = Query(30, ge=5, le=100),
    min_volume_usd: float = Query(500_000, ge=0),
    action_filter: Optional[str] = Query(None, description="BUY, SELL, or HOLD"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    import asyncio
    from app.services.defi_service import DeFiService, ARBITRUM_KNOWN_TOKENS

    exchange = ExchangeService()
    try:
        all_tickers = await exchange.get_all_tickers(min_turnover_usd=min_volume_usd)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Bybit fetch failed: {str(e)}")

    altcoins = [t for t in all_tickers if t["symbol"] not in _LARGE_CAPS]

    # DeFi-only scan: filter to tokens on user's configured network
    # Uses static registry + in-memory cache ONLY — no live DexScreener calls (avoids timeout)
    s_row = (await db.execute(select(Settings).where(Settings.user_id == user_id))).scalar_one_or_none()
    if s_row and s_row.defi_enabled and s_row.defi_only_scan:
        defi_net = s_row.defi_network or "arbitrum"
        from app.services.defi_service import _dexscreener_cache

        def _in_static_or_cache(sym: str) -> bool:
            if defi_net == "arbitrum" and sym in ARBITRUM_KNOWN_TOKENS:
                return True
            # Accept only already-cached positive results — no new API calls during scan
            cached = _dexscreener_cache.get(f"strict:{defi_net}:{sym}")
            return bool(cached)

        altcoins = [t for t in altcoins if _in_static_or_cache(t["symbol"])]

    results = []
    for t in altcoins:
        change = float(t.get("change_24h") or 0.0)
        score = change / 100.0

        if score >= 0.002:
            action = "STRONG_BUY" if score >= 0.01 else "BUY"
            sentiment = "BULLISH"
        elif score <= -0.002:
            action = "STRONG_SELL" if score <= -0.01 else "SELL"
            sentiment = "BEARISH"
        else:
            action = "HOLD"
            sentiment = "SIDEWAYS"

        results.append({
            "symbol": t["symbol"],
            "price": t["price"],
            "change_24h": round(change, 2),
            "volume_24h": t.get("volume_24h", 0),
            "turnover_24h": t.get("turnover_24h", 0),
            "high_24h": t.get("high_24h", 0),
            "low_24h": t.get("low_24h", 0),
            "score": round(score, 4),
            "recommended_action": action,
            "sentiment": sentiment,
        })

    results.sort(key=lambda x: abs(x["score"]), reverse=True)
    top_results = results[:limit]

    # Persist top results to ai_analysis so Smart Chart watchlist populates
    ai_svc = AIService(db)
    for r in top_results:
        is_buy = r["recommended_action"] in {"BUY", "STRONG_BUY"}
        is_sell = r["recommended_action"] in {"SELL", "STRONG_SELL"}
        price = float(r["price"] or 0.0)
        sl = round(price * (0.985 if is_buy else 1.015 if is_sell else 0.990), 8)
        tp = round(price * (1.030 if is_buy else 0.970 if is_sell else 1.010), 8)
        await ai_svc.save_heuristic_result(
            r["symbol"],
            {
                "trend": r["sentiment"],
                "sentiment": r["recommended_action"],
                "confidence": min(abs(r["score"]) * 10, 0.95),
                "analysis_text": f"Altcoin scan: 24h {r['change_24h']:+.2f}%, score {r['score']:.4f}",
                "price_at_analysis": price,
                "recommended_action": r["recommended_action"],
                "suggested_entry": price,
                "suggested_sl": sl,
                "suggested_tp": tp,
            },
            {
                "price": price,
                "change_24h": r["change_24h"],
                "volume_24h": r.get("volume_24h", 0),
                "turnover_24h": r.get("turnover_24h", 0),
            },
        )
    try:
        await db.commit()
    except Exception:
        await db.rollback()

    # Auto-add BUY/STRONG_BUY coins to spot_watchlist (upsert by symbol)
    try:
        from app.models.spot_watchlist import SpotWatchlist
        buy_results = [r for r in top_results if r["recommended_action"] in {"BUY", "STRONG_BUY"}]
        if buy_results:
            base_symbols = [r["symbol"].replace("USDT", "") for r in buy_results]
            existing_r = await db.execute(
                select(SpotWatchlist.symbol).where(
                    SpotWatchlist.user_id == user_id,
                    SpotWatchlist.symbol.in_(base_symbols),
                )
            )
            existing_symbols = {row[0] for row in existing_r.fetchall()}
            for r, sym in zip(buy_results, base_symbols):
                if sym not in existing_symbols:
                    price = float(r.get("price") or 0.0)
                    db.add(SpotWatchlist(
                        user_id=user_id,
                        symbol=sym,
                        network="arbitrum",
                        alert_enabled=True,
                        target_buy_price=round(price, 8) if price > 0 else None,
                        target_sell_price=round(price * 1.05, 8) if price > 0 else None,
                        notes=f"Auto: {r['recommended_action']} {r.get('change_24h', 0):+.2f}% 24h",
                    ))
            await db.commit()
    except Exception:
        await db.rollback()

    # Apply action_filter for the API response (save already done for all top coins)
    filtered = top_results
    if action_filter:
        af = action_filter.upper()
        if af == "BUY":
            filtered = [r for r in top_results if r["recommended_action"] in {"BUY", "STRONG_BUY"}]
        elif af == "SELL":
            filtered = [r for r in top_results if r["recommended_action"] in {"SELL", "STRONG_SELL"}]
        elif af == "HOLD":
            filtered = [r for r in top_results if r["recommended_action"] == "HOLD"]

    buy_count = sum(1 for r in filtered if r["recommended_action"] in {"BUY", "STRONG_BUY"})
    sell_count = sum(1 for r in filtered if r["recommended_action"] in {"SELL", "STRONG_SELL"})

    return {
        "altcoins": filtered,
        "total": len(filtered),
        "scanned": len(altcoins),
        "buy_signals": buy_count,
        "sell_signals": sell_count,
    }
