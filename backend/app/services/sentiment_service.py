"""
Multi-source market sentiment aggregator.
Sources:
  - Fear & Greed Index (alternative.me/fng) — cached 1h
  - CoinGecko Trending     (api.coingecko.com) — cached 15min

Composite score in [-0.5, +0.5]:
  0.0  = neutral
  +0.5 = max bullish
  -0.5 = max bearish

Formula when Polymarket data exists:
  composite = polymarket * 0.50 + fear_greed * 0.35 + trending_bonus * 0.15

Formula when no Polymarket markets found:
  composite = fear_greed * 0.85 + trending_bonus * 0.15
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from app.core.logging_config import get_logger

logger = get_logger(__name__)

_SSL_VERIFY = False  # match project-wide pattern


class SentimentService:
    _cache: dict = {}  # class-level shared TTL cache

    FNG_URL = "https://api.alternative.me/fng/?limit=1"
    COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
    FNG_TTL = 3600     # 1h — fear/greed changes slowly
    TRENDING_TTL = 900  # 15min

    # ── Internal cache helper ──────────────────────────────────────────────────

    async def _cached_fetch(self, key: str, ttl: int, fetcher) -> Optional[object]:
        entry = SentimentService._cache.get(key)
        if entry and time.monotonic() - entry["ts"] < ttl:
            return entry["data"]
        try:
            data = await fetcher()
            SentimentService._cache[key] = {"ts": time.monotonic(), "data": data}
            return data
        except Exception as exc:
            logger.warning("sentiment_fetch_failed", key=key, error=str(exc))
            return entry["data"] if entry else None

    # ── Fear & Greed ───────────────────────────────────────────────────────────

    async def get_fear_greed_raw(self) -> Optional[dict]:
        """Returns {"value": int(0-100), "classification": str}."""
        async def _fetch():
            async with httpx.AsyncClient(timeout=10.0, verify=_SSL_VERIFY) as client:
                resp = await client.get(self.FNG_URL)
                resp.raise_for_status()
                data = resp.json()
            item = (data.get("data") or [{}])[0]
            return {
                "value": int(item.get("value", 50)),
                "classification": item.get("value_classification", "Neutral"),
            }
        return await self._cached_fetch("fng", self.FNG_TTL, _fetch)

    async def get_fear_greed_score(self) -> float:
        """Normalized to [-0.5, +0.5]. 0.0 = neutral (value=50)."""
        raw = await self.get_fear_greed_raw()
        if raw is None:
            return 0.0
        return (raw["value"] - 50) / 100.0

    # ── CoinGecko Trending ─────────────────────────────────────────────────────

    async def get_trending_symbols(self) -> set[str]:
        """Returns set of uppercase base symbols in CoinGecko top-trending."""
        async def _fetch():
            async with httpx.AsyncClient(timeout=10.0, verify=_SSL_VERIFY) as client:
                resp = await client.get(self.COINGECKO_TRENDING_URL)
                resp.raise_for_status()
                data = resp.json()
            coins = data.get("coins") or []
            return [
                c["item"]["symbol"].upper()
                for c in coins
                if isinstance(c.get("item"), dict) and c["item"].get("symbol")
            ]
        result = await self._cached_fetch("cg_trending", self.TRENDING_TTL, _fetch)
        return set(result) if isinstance(result, list) else set()

    # ── Composite ──────────────────────────────────────────────────────────────

    async def get_sentiment_data(self) -> dict:
        """Fetch all sources in parallel. Returns metadata dict for API/display."""
        results = await asyncio.gather(
            self.get_fear_greed_raw(),
            self.get_trending_symbols(),
            return_exceptions=True,
        )
        fng_raw = results[0] if isinstance(results[0], dict) else None
        trending = results[1] if isinstance(results[1], set) else set()

        fng_value = fng_raw["value"] if fng_raw else 50
        fng_class = fng_raw["classification"] if fng_raw else "Neutral"
        fng_score = (fng_value - 50) / 100.0

        return {
            "fear_greed_value": fng_value,
            "fear_greed_classification": fng_class,
            "fear_greed_score": round(fng_score, 4),
            "trending_symbols": sorted(trending),
        }

    def compute_composite(
        self,
        symbol: str,
        polymarket_score: float,
        polymarket_count: int,
        fng_score: float,
        trending_symbols: set,
    ) -> tuple[float, dict]:
        """
        Blend Polymarket + Fear&Greed + trending into composite [-0.5, +0.5].
        Returns (composite, debug_metadata).
        """
        base_sym = symbol.replace("USDT", "").replace("USDC", "").upper()
        is_trending = base_sym in trending_symbols
        trending_bonus = 0.10 if is_trending else 0.0

        if polymarket_count > 0:
            composite = (
                polymarket_score * 0.50
                + fng_score * 0.35
                + trending_bonus * 0.15
            )
        else:
            composite = fng_score * 0.85 + trending_bonus * 0.15

        return round(composite, 4), {
            "polymarket_score": polymarket_score,
            "polymarket_count": polymarket_count,
            "fear_greed_score": fng_score,
            "is_trending": is_trending,
            "composite_sentiment": round(composite, 4),
        }
