import httpx
import json
import time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.ai_analysis import AIAnalysis
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

ANALYSIS_PROMPT_TEMPLATE = """You are an expert crypto trading analyst. Analyze this coin for paper trading using Bybit real market data plus Polymarket sentiment context.

Current Market Data:
- Symbol: {symbol}
- Current Price: {price}
- 24h Change: {change_24h}%
- Volume 24h: {volume_24h}
- High 24h: {high_24h}
- Low 24h: {low_24h}

Recent Price Action:
{recent_candles}

Polymarket Sentiment Context:
- Bias Score: {polymarket_bias_score}
- Related Market Count: {polymarket_market_count}
- Related Markets:
{polymarket_markets}

Strategy Parameters:
- Default Stop Loss Reference: {stop_loss}
- Default Take Profit Reference: {take_profit}
- Risk per Trade: {risk_percent}%

Use Polymarket as sentiment/context only, and Bybit price data for trade execution logic.

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{{
  "trend": "BULLISH|BEARISH|SIDEWAYS",
  "sentiment": "STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL",
  "confidence": 0.0,
  "support_levels": [0.0],
  "resistance_levels": [0.0],
  "recommended_action": "BUY|SELL|HOLD",
  "suggested_entry": 0.0,
  "suggested_sl": 0.0,
  "suggested_tp": 0.0,
  "reasoning": "Brief explanation"
}}"""


class AIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._use_deepseek_api = bool(settings.DEEPSEEK_API_KEY)

    def _build_prompt(self, symbol: str, market_data: dict) -> str:
        return ANALYSIS_PROMPT_TEMPLATE.format(
            symbol=symbol,
            price=market_data.get("price", 0),
            change_24h=market_data.get("change_24h", 0),
            volume_24h=market_data.get("volume_24h", 0),
            high_24h=market_data.get("high_24h", 0),
            low_24h=market_data.get("low_24h", 0),
            recent_candles=json.dumps(market_data.get("candles", []), indent=2),
            polymarket_bias_score=market_data.get("polymarket_bias_score", 0),
            polymarket_market_count=market_data.get("polymarket_market_count", 0),
            polymarket_markets=json.dumps(market_data.get("polymarket_markets", []), indent=2),
            stop_loss=settings.DEFAULT_STOP_LOSS,
            take_profit=settings.DEFAULT_TAKE_PROFIT,
            risk_percent=settings.DEFAULT_RISK_PERCENT,
        )

    async def _call_deepseek_api(self, prompt: str) -> tuple[str, int]:
        """Call DeepSeek Cloud API (OpenAI-compatible)."""
        start = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            elapsed_ms = int((time.time() - start) * 1000)
            logger.info("deepseek_api_call", model=settings.DEEPSEEK_MODEL,
                        tokens=data.get("usage", {}), time_ms=elapsed_ms)
            return text, elapsed_ms

    async def _call_ollama(self, prompt: str) -> tuple[str, int]:
        """Call local Ollama instance."""
        start = time.time()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data = response.json()
            elapsed_ms = int((time.time() - start) * 1000)
            return data.get("response", ""), elapsed_ms

    async def _call_ai(self, prompt: str) -> tuple[str, int]:
        if self._use_deepseek_api:
            return await self._call_deepseek_api(prompt)
        return await self._call_ollama(prompt)

    def _get_model_name(self) -> str:
        if self._use_deepseek_api:
            return f"deepseek-api/{settings.DEEPSEEK_MODEL}"
        return f"ollama/{settings.OLLAMA_MODEL}"

    def _parse_response(self, raw: str) -> dict:
        try:
            # DeepSeek API with json_object mode returns clean JSON
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Fallback: extract JSON block from prose (Ollama)
        try:
            start_idx = raw.find("{")
            end_idx = raw.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                return json.loads(raw[start_idx:end_idx])
        except json.JSONDecodeError:
            logger.warning("ai_parse_error", raw=raw[:200])
        return {}

    async def analyze_market(self, symbol: str, market_data: dict) -> AIAnalysis:
        prompt = self._build_prompt(symbol, market_data)

        try:
            raw_response, processing_time = await self._call_ai(prompt)
        except Exception as e:
            logger.error("ai_call_error", provider="deepseek_api" if self._use_deepseek_api else "ollama",
                         error=str(e))
            raise

        parsed = self._parse_response(raw_response)

        analysis = AIAnalysis(
            symbol=symbol,
            model_name=self._get_model_name(),
            trend=parsed.get("trend"),
            sentiment=parsed.get("sentiment"),
            confidence=parsed.get("confidence"),
            support_levels=parsed.get("support_levels"),
            resistance_levels=parsed.get("resistance_levels"),
            key_levels=parsed.get("key_levels"),
            analysis_text=parsed.get("reasoning", raw_response),
            raw_response=raw_response,
            market_data_snapshot=market_data,
            price_at_analysis=market_data.get("price"),
            recommended_action=parsed.get("recommended_action"),
            suggested_entry=parsed.get("suggested_entry"),
            suggested_sl=parsed.get("suggested_sl"),
            suggested_tp=parsed.get("suggested_tp"),
            processing_time_ms=processing_time,
        )
        self.db.add(analysis)
        await self.db.flush()
        await self.db.refresh(analysis)

        logger.info("ai_analysis_complete", symbol=symbol, action=analysis.recommended_action,
                    confidence=analysis.confidence, time_ms=processing_time,
                    provider="deepseek_api" if self._use_deepseek_api else "ollama")
        return analysis

    async def save_heuristic_result(self, symbol: str, opportunity: dict, market_data: dict) -> None:
        """Save heuristic scan result to AIAnalysis table without an AI call."""
        analysis = AIAnalysis(
            symbol=symbol,
            model_name="heuristic",
            trend=opportunity.get("trend"),
            sentiment=opportunity.get("sentiment"),
            confidence=opportunity.get("confidence"),
            analysis_text=opportunity.get("analysis_text", ""),
            market_data_snapshot=market_data,
            price_at_analysis=opportunity.get("price_at_analysis"),
            recommended_action=opportunity.get("recommended_action"),
            suggested_entry=opportunity.get("suggested_entry"),
            suggested_sl=opportunity.get("suggested_sl"),
            suggested_tp=opportunity.get("suggested_tp"),
            processing_time_ms=0,
        )
        self.db.add(analysis)

    async def get_latest_analysis(self, symbol: str) -> Optional[AIAnalysis]:
        result = await self.db.execute(
            select(AIAnalysis)
            .where(AIAnalysis.symbol == symbol)
            .order_by(desc(AIAnalysis.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_analysis_history(self, symbol: str, limit: int = 20) -> list[AIAnalysis]:
        result = await self.db.execute(
            select(AIAnalysis)
            .where(AIAnalysis.symbol == symbol)
            .order_by(desc(AIAnalysis.created_at))
            .limit(limit)
        )
        return result.scalars().all()
