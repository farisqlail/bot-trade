from typing import Optional
import httpx
from app.core.logging_config import get_logger

logger = get_logger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

SYMBOL_TO_ID: dict[str, str] = {
    "ARB": "arbitrum",
    "UNI": "uniswap",
    "GMX": "gmx",
    "LINK": "chainlink",
    "AAVE": "aave",
    "PENDLE": "pendle",
    "RDNT": "radiant-capital",
    "WIF": "dogwifcoin",
    "PEPE": "pepe",
    "BONK": "bonk",
}


class SpotMarketService:
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    def _resolve_id(self, symbol: str) -> Optional[str]:
        return SYMBOL_TO_ID.get(symbol.upper())

    async def get_token_price(self, symbol: str) -> Optional[dict]:
        coingecko_id = self._resolve_id(symbol)
        if not coingecko_id:
            logger.warning("spot_price_unknown_symbol", symbol=symbol)
            return None

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{COINGECKO_BASE}/simple/price",
                    params={
                        "ids": coingecko_id,
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_24hr_vol": "true",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            token_data = data.get(coingecko_id)
            if not token_data:
                logger.warning("spot_price_no_data", symbol=symbol, coingecko_id=coingecko_id)
                return None

            result = {
                "symbol": symbol.upper(),
                "price": float(token_data.get("usd") or 0.0),
                "change_24h": float(token_data.get("usd_24h_change") or 0.0),
                "volume_24h": float(token_data.get("usd_24h_vol") or 0.0),
            }
            logger.info("spot_price_fetched", symbol=symbol, price=result["price"])
            return result

        except httpx.HTTPStatusError as e:
            logger.warning("spot_price_http_error", symbol=symbol, status=e.response.status_code)
            return None
        except Exception as e:
            logger.warning("spot_price_error", symbol=symbol, error=str(e))
            return None

    async def get_multiple_prices(self, symbols: list[str]) -> list[dict]:
        known = {s.upper(): self._resolve_id(s) for s in symbols}
        id_to_symbol = {v: k for k, v in known.items() if v}

        if not id_to_symbol:
            logger.warning("spot_multi_price_no_known_symbols", symbols=symbols)
            return []

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{COINGECKO_BASE}/simple/price",
                    params={
                        "ids": ",".join(id_to_symbol.keys()),
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_24hr_vol": "true",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for coingecko_id, sym in id_to_symbol.items():
                token_data = data.get(coingecko_id)
                if not token_data:
                    logger.warning("spot_multi_price_missing", symbol=sym)
                    continue
                results.append({
                    "symbol": sym,
                    "price": float(token_data.get("usd") or 0.0),
                    "change_24h": float(token_data.get("usd_24h_change") or 0.0),
                    "volume_24h": float(token_data.get("usd_24h_vol") or 0.0),
                })

            logger.info("spot_multi_price_fetched", count=len(results))
            return results

        except httpx.HTTPStatusError as e:
            logger.warning("spot_multi_price_http_error", status=e.response.status_code)
            return []
        except Exception as e:
            logger.warning("spot_multi_price_error", error=str(e))
            return []

    def analyze_spot_signal(self, symbol: str, price_data: dict) -> dict:
        """Momentum-based signal — identical labels/thresholds as altcoin scanner."""
        change = float(price_data.get("change_24h") or 0.0)
        price = float(price_data.get("price") or 0.0)
        score = change / 100.0

        if score >= 0.01:
            signal = "STRONG_BUY"
            reason = f"Up {change:.1f}% in 24h — strong momentum"
        elif score >= 0.002:
            signal = "BUY"
            reason = f"Up {change:.1f}% in 24h — positive momentum"
        elif score <= -0.01:
            signal = "STRONG_SELL"
            reason = f"Down {abs(change):.1f}% in 24h — strong sell pressure"
        elif score <= -0.002:
            signal = "SELL"
            reason = f"Down {abs(change):.1f}% in 24h — negative momentum"
        else:
            signal = "HOLD"
            reason = f"24h change {change:+.1f}% — no clear signal"

        result = {
            "symbol": symbol.upper(),
            "signal": signal,
            "price": price,
            "change_24h": round(change, 2),
            "reason": reason,
        }
        logger.info("spot_signal_analyzed", symbol=symbol, signal=signal, change_24h=change)
        return result

    def calculate_pnl(self, buy_price: float, sell_price: float, amount: float) -> dict:
        if buy_price <= 0:
            logger.warning("spot_pnl_invalid_buy_price", buy_price=buy_price)
            return {"pnl_usd": 0.0, "pnl_percent": 0.0}

        pnl_usd = (sell_price - buy_price) * amount
        pnl_percent = ((sell_price - buy_price) / buy_price) * 100

        result = {
            "pnl_usd": round(pnl_usd, 6),
            "pnl_percent": round(pnl_percent, 4),
        }
        logger.info(
            "spot_pnl_calculated",
            buy_price=buy_price,
            sell_price=sell_price,
            amount=amount,
            pnl_usd=result["pnl_usd"],
            pnl_percent=result["pnl_percent"],
        )
        return result
