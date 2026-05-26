import asyncio
import json

import certifi
import httpx

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# SSL verification setting: use certifi CA bundle by default, or disable if BYBIT_VERIFY_SSL=False
_SSL_VERIFY = certifi.where() if settings.BYBIT_VERIFY_SSL else False


class ExchangeService:
    """Bybit public market data + Polymarket sentiment context."""

    DEFAULT_WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]
    POLYMARKET_QUERIES = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum",
        "SOLUSDT": "solana",
        "XRPUSDT": "ripple",
        "DOGEUSDT": "dogecoin",
        "BNBUSDT": "bnb",
        "ADAUSDT": "cardano",
        "LINKUSDT": "chainlink",
        "AVAXUSDT": "avalanche",
        "SUIUSDT": "sui",
    }
    POSITIVE_HINTS = ("above", "over", "reach", "exceed", "higher", "up", "bull", "surge", "gain")
    NEGATIVE_HINTS = ("below", "under", "drop", "crash", "down", "bear", "fall", "reject", "lose")

    def __init__(self, api_key: str = "", api_secret: str = "", public_data_only: bool = True):
        self.api_key = api_key or settings.BYBIT_API_KEY
        self.api_secret = api_secret or settings.BYBIT_API_SECRET
        self.public_data_only = public_data_only
        self.bybit_base_url = settings.BYBIT_BASE_URL.rstrip("/")
        self.gamma_base_url = settings.POLYMARKET_GAMMA_BASE_URL.rstrip("/")

    def _use_mock_balance(self) -> bool:
        placeholder_values = {
            "",
            "your-bybit-api-key",
            "your_bybit_api_key",
            "changeme",
        }
        return self.api_key.strip().lower() in placeholder_values

    def _safe_json_array(self, value):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return []

    def get_watchlist(self, raw_watchlist=None) -> list[str]:
        if isinstance(raw_watchlist, str):
            values = [item.strip().upper() for item in raw_watchlist.split(",") if item.strip()]
            return values or self.DEFAULT_WATCHLIST
        if isinstance(raw_watchlist, list):
            values = [str(item).strip().upper() for item in raw_watchlist if str(item).strip()]
            return values or self.DEFAULT_WATCHLIST
        return self.DEFAULT_WATCHLIST

    async def get_all_tickers(self, min_turnover_usd: float = 0.0) -> list[dict]:
        """One batch call → all active linear USDT perpetuals sorted by turnover."""
        async with httpx.AsyncClient(timeout=30.0, verify=_SSL_VERIFY) as client:
            response = await client.get(
                f"{self.bybit_base_url}/v5/market/tickers",
                params={"category": "linear"},
            )
            response.raise_for_status()
            payload = response.json()

        items = (payload.get("result") or {}).get("list") or []
        tickers = []
        for data in items:
            symbol = data.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            try:
                price = float(data["lastPrice"])
                change_24h = float(data.get("price24hPcnt") or 0.0) * 100
                volume_24h = float(data.get("volume24h") or 0.0)
                turnover_24h = float(data.get("turnover24h") or 0.0)
            except (ValueError, KeyError):
                continue
            if price <= 0 or turnover_24h < min_turnover_usd:
                continue
            tickers.append({
                "symbol": symbol,
                "price": price,
                "change_24h": change_24h,
                "volume_24h": volume_24h,
                "turnover_24h": turnover_24h,
                "high_24h": float(data.get("highPrice24h") or 0.0),
                "low_24h": float(data.get("lowPrice24h") or 0.0),
            })
        tickers.sort(key=lambda t: abs(t["change_24h"]), reverse=True)
        return tickers

    async def get_ticker(self, symbol: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0, verify=_SSL_VERIFY) as client:
            response = await client.get(
                f"{self.bybit_base_url}/v5/market/tickers",
                params={"category": "linear", "symbol": symbol.upper()},
            )
            response.raise_for_status()
            payload = response.json()

        items = ((payload.get("result") or {}).get("list") or [])
        if not items:
            raise ValueError(f"No Bybit ticker data for {symbol}")
        data = items[0]
        return {
            "symbol": data["symbol"],
            "price": float(data["lastPrice"]),
            "change_24h": float(data.get("price24hPcnt") or 0.0) * 100,
            "volume_24h": float(data.get("volume24h") or 0.0),
            "high_24h": float(data.get("highPrice24h") or 0.0),
            "low_24h": float(data.get("lowPrice24h") or 0.0),
        }

    async def get_klines(self, symbol: str, interval: str = "60", limit: int = 10) -> list:
        async with httpx.AsyncClient(timeout=30.0, verify=_SSL_VERIFY) as client:
            response = await client.get(
                f"{self.bybit_base_url}/v5/market/kline",
                params={
                    "category": "linear",
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            payload = response.json()

        rows = ((payload.get("result") or {}).get("list") or [])
        candles = [
            {
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in rows
        ]
        candles.sort(key=lambda candle: candle["open_time"])
        return candles

    async def _search_polymarket_context(self, symbol: str) -> dict:
        query = self.POLYMARKET_QUERIES.get(symbol.upper(), symbol.replace("USDT", "").lower())
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=_SSL_VERIFY) as client:
                response = await client.get(
                    f"{self.gamma_base_url}/public-search",
                    params={
                        "q": query,
                        "events_status": "active",
                        "limit_per_type": 5,
                        "search_profiles": "false",
                        "search_tags": "false",
                    },
                )
                if response.status_code >= 400:
                    return {"polymarket_bias_score": 0.0, "polymarket_market_count": 0, "polymarket_markets": []}
                payload = response.json()
        except Exception as exc:
            logger.warning("polymarket_context_fetch_failed", symbol=symbol, error=str(exc))
            return {"polymarket_bias_score": 0.0, "polymarket_market_count": 0, "polymarket_markets": []}

        events = payload.get("events") or []
        relevant = []
        weighted_sum = 0.0
        total_weight = 0.0

        for event in events:
            for market in event.get("markets") or []:
                if market.get("closed") is True:
                    continue
                question = (market.get("question") or "").strip()
                outcome_prices = [float(p) for p in self._safe_json_array(market.get("outcomePrices")) if p is not None]
                if not question or not outcome_prices:
                    continue

                yes_price = outcome_prices[0]
                lower_question = question.lower()
                if any(token in lower_question for token in self.POSITIVE_HINTS):
                    bias = yes_price - 0.5
                elif any(token in lower_question for token in self.NEGATIVE_HINTS):
                    bias = 0.5 - yes_price
                else:
                    bias = yes_price - 0.5

                weight = float(
                    market.get("volume24hrClob")
                    or market.get("volume24hr")
                    or market.get("volume")
                    or 1.0
                )
                weighted_sum += bias * max(weight, 1.0)
                total_weight += max(weight, 1.0)
                relevant.append(
                    {
                        "question": question,
                        "yes_price": yes_price,
                        "bias": round(bias, 4),
                        "volume_24h": weight,
                    }
                )

        relevant.sort(key=lambda item: abs(item["bias"]) * item["volume_24h"], reverse=True)
        return {
            "polymarket_bias_score": round(weighted_sum / total_weight, 4) if total_weight else 0.0,
            "polymarket_market_count": len(relevant),
            "polymarket_markets": relevant[:5],
        }

    async def get_account_balance(self) -> dict:
        if self._use_mock_balance():
            return {
                "balance": 10000.0,
                "equity": 10000.0,
                "unrealized_pnl": 0.0,
                "margin_used": 0.0,
                "free_margin": 10000.0,
            }

        logger.warning("bybit_private_balance_calls_not_implemented_fallback_mock_balance")
        return {
            "balance": 10000.0,
            "equity": 10000.0,
            "unrealized_pnl": 0.0,
            "margin_used": 0.0,
            "free_margin": 10000.0,
        }

    async def get_market_data(self, symbol: str) -> dict:
        ticker, candles, polymarket = await asyncio.gather(
            self.get_ticker(symbol),
            self.get_klines(symbol),
            self._search_polymarket_context(symbol),
        )
        ticker["candles"] = candles
        ticker.update(polymarket)
        return ticker
