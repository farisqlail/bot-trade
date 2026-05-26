import hashlib
import hmac
import json
import time

import certifi
import httpx

from app.config import settings as global_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_SSL_VERIFY = certifi.where() if global_settings.BYBIT_VERIFY_SSL else False


class BybitOrderService:
    """Bybit V5 private API — order placement and account management."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = (
            "https://api-testnet.bybit.com"
            if testnet
            else global_settings.BYBIT_BASE_URL.rstrip("/")
        )

    def _sign_get(self, query_string: str) -> dict:
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        sign_payload = timestamp + self.api_key + recv_window + query_string
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
        }

    def _sign_post(self, body_str: str) -> dict:
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        sign_payload = timestamp + self.api_key + recv_window + body_str
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json",
        }

    async def get_wallet_balance(self, coin: str = "USDT") -> float:
        params = {"accountType": "UNIFIED", "coin": coin}
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        headers = self._sign_get(qs)
        async with httpx.AsyncClient(timeout=15.0, verify=_SSL_VERIFY) as client:
            resp = await client.get(
                f"{self.base_url}/v5/account/wallet-balance",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        coins = (
            ((data.get("result") or {}).get("list") or [{}])[0].get("coin") or []
        )
        for c in coins:
            if c.get("coin") == coin:
                try:
                    return float(c.get("availableToWithdraw") or c.get("walletBalance") or 0.0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    async def set_leverage(self, symbol: str, leverage: int, category: str = "linear") -> None:
        body = {
            "category": category,
            "symbol": symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage),
        }
        body_str = json.dumps(body, separators=(",", ":"))
        headers = self._sign_post(body_str)
        async with httpx.AsyncClient(timeout=15.0, verify=_SSL_VERIFY) as client:
            resp = await client.post(
                f"{self.base_url}/v5/position/set-leverage",
                content=body_str,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("retCode") not in {0, 110043}:
            logger.warning("bybit_set_leverage_error", symbol=symbol, ret=data.get("retCode"), msg=data.get("retMsg"))

    async def place_order(
        self,
        symbol: str,
        side: str,
        qty: str,
        order_type: str = "Market",
        stop_loss: float | None = None,
        take_profit: float | None = None,
        category: str = "linear",
    ) -> dict:
        body: dict = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty,
            "timeInForce": "IOC",
        }
        if stop_loss:
            body["stopLoss"] = str(round(stop_loss, 6))
        if take_profit:
            body["takeProfit"] = str(round(take_profit, 6))

        body_str = json.dumps(body, separators=(",", ":"))
        headers = self._sign_post(body_str)

        async with httpx.AsyncClient(timeout=20.0, verify=_SSL_VERIFY) as client:
            resp = await client.post(
                f"{self.base_url}/v5/order/create",
                content=body_str,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("retCode") != 0:
            raise ValueError(f"Bybit order error {data.get('retCode')}: {data.get('retMsg')}")

        return data.get("result") or {}

    async def get_positions(self, symbol: str | None = None, category: str = "linear") -> list[dict]:
        params: dict = {"category": category, "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = symbol
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        headers = self._sign_get(qs)
        async with httpx.AsyncClient(timeout=15.0, verify=_SSL_VERIFY) as client:
            resp = await client.get(
                f"{self.base_url}/v5/position/list",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        return (data.get("result") or {}).get("list") or []
