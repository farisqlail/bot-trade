from fastapi import APIRouter

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("")
async def get_market_sentiment():
    """Return current Fear & Greed Index + CoinGecko trending symbols."""
    from app.services.sentiment_service import SentimentService
    svc = SentimentService()
    return await svc.get_sentiment_data()
