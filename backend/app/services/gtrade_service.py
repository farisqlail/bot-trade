import asyncio
import aiohttp
import time
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from typing import Optional

from app.core.logging_config import get_logger
from app.config import settings as app_settings
from app.utils.crypto import decrypt as _crypto_decrypt

logger = get_logger(__name__)

ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"
GTRADE_DIAMOND = "0xFF162c694eAA571f685030649814522eE509D7E8"
GTRADE_USDC = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
GTRADE_API_URL = "https://backend-arbitrum.gains.trade"
CHAIN_ID = 42161

# Static fallback — used when API fetch fails
GTRADE_PAIRS = {
    "BTC/USDT": {"index": 0, "name": "BTC/USD", "max_leverage": 150},
    "ETH/USDT": {"index": 1, "name": "ETH/USD", "max_leverage": 150},
    "LINK/USDT": {"index": 2, "name": "LINK/USD", "max_leverage": 150},
    "DOGE/USDT": {"index": 3, "name": "DOGE/USD", "max_leverage": 150},
    "SOL/USDT": {"index": 4, "name": "SOL/USD", "max_leverage": 150},
    "BNB/USDT": {"index": 5, "name": "BNB/USD", "max_leverage": 150},
    "XRP/USDT": {"index": 6, "name": "XRP/USD", "max_leverage": 150},
    "AVAX/USDT": {"index": 9, "name": "AVAX/USD", "max_leverage": 150},
    "ARB/USDT": {"index": 11, "name": "ARB/USD", "max_leverage": 150},
    "MATIC/USDT": {"index": 14, "name": "MATIC/USD", "max_leverage": 150},
}

# Module-level cache populated by fetch_pairs_from_api()
_PAIRS_API_CACHE: dict = {}
_PAIRS_CACHE_TS: float = 0
_PAIRS_CACHE_TTL: float = 3600  # 1 hour

GTRADE_ABI = [
    {
        "name": "openTrade",
        "type": "function",
        "inputs": [
            {
                "name": "_trade",
                "type": "tuple",
                "components": [
                    {"name": "trader", "type": "address"},
                    {"name": "pairIndex", "type": "uint256"},
                    {"name": "index", "type": "uint256"},
                    {"name": "initialPosToken", "type": "uint256"},
                    {"name": "positionSizeDai", "type": "uint256"},
                    {"name": "openPrice", "type": "uint256"},
                    {"name": "buy", "type": "bool"},
                    {"name": "leverage", "type": "uint256"},
                    {"name": "tp", "type": "uint256"},
                    {"name": "sl", "type": "uint256"},
                ],
            },
            {"name": "_type", "type": "uint8"},
            {"name": "_slippageP", "type": "uint256"},
            {"name": "_referral", "type": "address"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "closeTradeMarket",
        "type": "function",
        "inputs": [
            {"name": "_pairIndex", "type": "uint256"},
            {"name": "_index", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "updateTp",
        "type": "function",
        "inputs": [
            {"name": "_pairIndex", "type": "uint256"},
            {"name": "_index", "type": "uint256"},
            {"name": "_newTp", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "updateSl",
        "type": "function",
        "inputs": [
            {"name": "_pairIndex", "type": "uint256"},
            {"name": "_index", "type": "uint256"},
            {"name": "_newSl", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
]

USDC_ABI = [
    {
        "name": "approve",
        "type": "function",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "name": "allowance",
        "type": "function",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
    },
]


class GTradeService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
        try:
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        except Exception:
            pass
    def _decrypt_key(self, encrypted: str) -> str:
        return _crypto_decrypt(encrypted.strip()).strip()

    async def fetch_pairs_from_api(self) -> dict:
        """Fetch all crypto pairs from Gains Network API. Caches for 1h. Falls back to GTRADE_PAIRS."""
        global _PAIRS_API_CACHE, _PAIRS_CACHE_TS
        now = time.time()
        if _PAIRS_API_CACHE and (now - _PAIRS_CACHE_TS) < _PAIRS_CACHE_TTL:
            return _PAIRS_API_CACHE

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{GTRADE_API_URL}/trading-variables",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"gTrade trading-variables returned {resp.status}")
                        return _PAIRS_API_CACHE or GTRADE_PAIRS
                    data = await resp.json()
        except Exception as e:
            logger.warning(f"gTrade fetch pairs failed: {e}")
            return _PAIRS_API_CACHE or GTRADE_PAIRS

        pairs_raw = data.get("pairs", [])
        pair_params = data.get("pairParams", [])
        groups = data.get("groups", [])

        # Max leverage: prefer pairParams, fallback to group maxLeverage
        def _max_lev(idx: int, group_idx: int) -> int:
            if idx < len(pair_params):
                lev = pair_params[idx].get("maxLeverage")
                if lev:
                    try:
                        return int(lev)
                    except Exception:
                        pass
            if group_idx < len(groups):
                lev = groups[group_idx].get("maxLeverage")
                if lev:
                    try:
                        return int(lev)
                    except Exception:
                        pass
            return 150

        result = {}
        for idx, pair in enumerate(pairs_raw):
            group_idx = int(pair.get("groupIndex", 99))
            if group_idx != 0:  # 0 = crypto
                continue
            from_sym = pair.get("from", "")
            to_sym = pair.get("to", "USD")
            if not from_sym or to_sym != "USD":
                continue
            key = f"{from_sym}/USDT"
            result[key] = {
                "index": idx,
                "name": f"{from_sym}/USD",
                "max_leverage": _max_lev(idx, group_idx),
            }

        if result:
            _PAIRS_API_CACHE = result
            _PAIRS_CACHE_TS = now
            logger.info(f"gTrade pairs cache updated: {len(result)} crypto pairs")
            return result

        logger.warning("gTrade API returned no crypto pairs, using static fallback")
        return GTRADE_PAIRS

    def get_active_pairs(self) -> dict:
        """Return cached dynamic pairs or static fallback."""
        return _PAIRS_API_CACHE if _PAIRS_API_CACHE else GTRADE_PAIRS

    def supports_symbol(self, symbol: str) -> bool:
        active = self.get_active_pairs()
        return symbol.upper() in active

    def get_pair_index(self, symbol: str) -> Optional[int]:
        active = self.get_active_pairs()
        info = active.get(symbol.upper())
        return info["index"] if info else None

    def _get_gas_price(self) -> int:
        raw = self.w3.eth.gas_price
        return int(raw * 1.3)

    async def _ensure_usdc_approved(self, account, amount_usdc: float) -> None:
        loop = asyncio.get_event_loop()
        usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(GTRADE_USDC),
            abi=USDC_ABI,
        )
        amount_units = int(amount_usdc * 1e6)
        allowance = await loop.run_in_executor(
            None,
            lambda: usdc_contract.functions.allowance(
                account.address,
                Web3.to_checksum_address(GTRADE_DIAMOND),
            ).call(),
        )
        if allowance >= amount_units:
            return

        gas_price = self._get_gas_price()
        nonce = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.get_transaction_count(account.address),
        )
        tx = usdc_contract.functions.approve(
            Web3.to_checksum_address(GTRADE_DIAMOND),
            2**256 - 1,
        ).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 100000,
            "maxFeePerGas": gas_price,
            "maxPriorityFeePerGas": int(gas_price * 0.1),
            "chainId": CHAIN_ID,
        })
        signed = account.sign_transaction(tx)
        tx_hash = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.send_raw_transaction(signed.raw_transaction),
        )
        await loop.run_in_executor(
            None,
            lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60),
        )
        logger.info(f"gTrade USDC approved: {tx_hash.hex()}")

    async def get_user_trades(self, wallet_address: str) -> list:
        # Try multiple endpoint formats across gTrade API versions
        endpoints = [
            f"{GTRADE_API_URL}/user/{wallet_address}/trades",
            f"{GTRADE_API_URL}/traders/{wallet_address}/trades",
            f"{GTRADE_API_URL}/v1/user/{wallet_address}/trades",
        ]
        for url in endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            result = data if isinstance(data, list) else (data.get("trades") or data.get("data") or [])
                            if result:
                                logger.info(f"gTrade API trades fetched from {url}: {len(result)} trades")
                                return result
            except Exception as e:
                logger.warning(f"gTrade API {url} failed: {e}")
        return []

    async def force_close_all(self, private_key: str, wallet_address: str) -> list:
        """Fetch real open positions from gTrade API and close all with correct indices."""
        trades = await self.get_user_trades(wallet_address)
        if not trades:
            raise ValueError("No open trades found on gTrade API. Position may already be closed or API unreachable.")

        results = []
        for t in trades:
            try:
                pair_index = int(t.get("pairIndex") or t.get("pair_index") or t.get("pairindex") or 0)
                trade_index = int(t.get("index") if t.get("index") is not None else (t.get("tradeIndex") or t.get("trade_index") or 0))
                result = await self.close_position(private_key, pair_index, trade_index)
                results.append({
                    "pair_index": pair_index,
                    "trade_index": trade_index,
                    "tx_hash": result.get("tx_hash"),
                    "status": "close_requested",
                })
                logger.info(f"gTrade force_close pairIndex={pair_index} tradeIndex={trade_index} tx={result.get('tx_hash')}")
            except Exception as e:
                results.append({
                    "pair_index": t.get("pairIndex"),
                    "trade_index": t.get("index"),
                    "error": str(e),
                })
        return results

    async def _get_trade_index(self, wallet_address: str, pair_index: int) -> int:
        # Retry up to 3 times — gTrade API may lag behind chain
        for attempt in range(3):
            if attempt > 0:
                await asyncio.sleep(2)
            trades = await self.get_user_trades(wallet_address)
            matching = []
            for t in trades:
                # gTrade API uses different field names across versions
                pi = t.get("pairIndex") or t.get("pair_index") or t.get("pairindex")
                idx = t.get("index") if t.get("index") is not None else t.get("tradeIndex") or t.get("trade_index") or 0
                if pi is not None and int(pi) == int(pair_index):
                    matching.append(int(idx))
            if matching:
                return max(matching)
        # Fallback: 0 (first slot, correct for most fresh wallets)
        logger.warning(f"gTrade trade index not found via API for pairIndex={pair_index}, defaulting to 0")
        return 0

    async def open_position(
        self,
        private_key: str,
        symbol: str,
        is_long: bool,
        collateral_usdc: float,
        leverage: float,
        current_price: float,
        tp_price_usd: Optional[float] = None,
        sl_price_usd: Optional[float] = None,
    ) -> dict:
        loop = asyncio.get_event_loop()
        account = Account.from_key(self._decrypt_key(private_key))

        pair_info = self.get_active_pairs().get(symbol.upper())
        if not pair_info:
            raise ValueError(f"Symbol {symbol} not supported by gTrade")

        pair_index = pair_info["index"]
        max_lev = pair_info["max_leverage"]
        leverage = min(float(leverage), float(max_lev))

        await self._ensure_usdc_approved(account, collateral_usdc * 2)

        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(GTRADE_DIAMOND),
            abi=GTRADE_ABI,
        )

        position_size_units = int(collateral_usdc * 1e6)
        open_price_units = int(current_price * 1e10)
        leverage_int = max(2, int(leverage))
        slippage_p = 500000000  # 5% = 5e8 in 1e10 precision

        tp_units = int(tp_price_usd * 1e10) if tp_price_usd and tp_price_usd > 0 else 0
        sl_units = int(sl_price_usd * 1e10) if sl_price_usd and sl_price_usd > 0 else 0

        trade_tuple = (
            account.address,      # trader
            pair_index,           # pairIndex
            0,                    # index (new trade)
            0,                    # initialPosToken
            position_size_units,  # positionSizeDai (USDC with 6 decimals)
            open_price_units,     # openPrice (1e10 precision)
            is_long,              # buy
            leverage_int,         # leverage
            tp_units,             # tp (0 = no on-chain TP)
            sl_units,             # sl (0 = no on-chain SL)
        )

        gas_price = self._get_gas_price()
        nonce = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.get_transaction_count(account.address),
        )

        tx = contract.functions.openTrade(
            trade_tuple,
            0,            # MARKET order type
            slippage_p,
            "0x0000000000000000000000000000000000000000",
        ).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 1500000,
            "maxFeePerGas": gas_price,
            "maxPriorityFeePerGas": int(gas_price * 0.1),
            "chainId": CHAIN_ID,
        })

        signed = account.sign_transaction(tx)
        tx_hash = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.send_raw_transaction(signed.raw_transaction),
        )
        logger.info(f"gTrade openTrade tx submitted: {tx_hash.hex()}")

        receipt = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120),
        )

        if receipt["status"] == 0:
            raise Exception(f"gTrade openTrade reverted: {tx_hash.hex()}")

        trade_index = await self._get_trade_index(account.address, pair_index)

        return {
            "status": "success",
            "tx_hash": tx_hash.hex(),
            "trade_index": trade_index,
            "size_usd": round(collateral_usdc * leverage, 2),
            "tp_price": tp_price_usd if tp_units else None,
            "sl_price": sl_price_usd if sl_units else None,
        }

    async def update_tpsl(
        self,
        private_key: str,
        pair_index: int,
        trade_index: int,
        tp_price_usd: Optional[float] = None,
        sl_price_usd: Optional[float] = None,
    ) -> dict:
        loop = asyncio.get_event_loop()
        account = Account.from_key(self._decrypt_key(private_key))

        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(GTRADE_DIAMOND),
            abi=GTRADE_ABI,
        )
        gas_price = self._get_gas_price()
        results = {}

        if tp_price_usd and tp_price_usd > 0:
            nonce = await loop.run_in_executor(None, lambda: self.w3.eth.get_transaction_count(account.address))
            tx = contract.functions.updateTp(
                pair_index, trade_index, int(tp_price_usd * 1e10)
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 300000,
                "maxFeePerGas": gas_price,
                "maxPriorityFeePerGas": int(gas_price * 0.1),
                "chainId": CHAIN_ID,
            })
            signed = account.sign_transaction(tx)
            tx_hash = await loop.run_in_executor(None, lambda: self.w3.eth.send_raw_transaction(signed.raw_transaction))
            await loop.run_in_executor(None, lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60))
            results["tp_tx"] = tx_hash.hex()
            logger.info(f"gTrade updateTp tx: {tx_hash.hex()}")

        if sl_price_usd and sl_price_usd > 0:
            nonce = await loop.run_in_executor(None, lambda: self.w3.eth.get_transaction_count(account.address))
            tx = contract.functions.updateSl(
                pair_index, trade_index, int(sl_price_usd * 1e10)
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 300000,
                "maxFeePerGas": gas_price,
                "maxPriorityFeePerGas": int(gas_price * 0.1),
                "chainId": CHAIN_ID,
            })
            signed = account.sign_transaction(tx)
            tx_hash = await loop.run_in_executor(None, lambda: self.w3.eth.send_raw_transaction(signed.raw_transaction))
            await loop.run_in_executor(None, lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60))
            results["sl_tx"] = tx_hash.hex()
            logger.info(f"gTrade updateSl tx: {tx_hash.hex()}")

        return {"status": "success", **results}

    async def close_position(
        self,
        private_key: str,
        pair_index: int,
        trade_index: int,
    ) -> dict:
        loop = asyncio.get_event_loop()
        account = Account.from_key(self._decrypt_key(private_key))

        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(GTRADE_DIAMOND),
            abi=GTRADE_ABI,
        )

        gas_price = self._get_gas_price()
        nonce = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.get_transaction_count(account.address),
        )

        tx = contract.functions.closeTradeMarket(
            pair_index,
            trade_index,
        ).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 800000,
            "maxFeePerGas": gas_price,
            "maxPriorityFeePerGas": int(gas_price * 0.1),
            "chainId": CHAIN_ID,
        })

        signed = account.sign_transaction(tx)
        tx_hash = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.send_raw_transaction(signed.raw_transaction),
        )
        logger.info(f"gTrade closeTradeMarket tx submitted: {tx_hash.hex()}")

        receipt = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120),
        )

        if receipt["status"] == 0:
            raise Exception(f"gTrade closeTradeMarket reverted: {tx_hash.hex()}")

        return {
            "status": "success",
            "tx_hash": tx_hash.hex(),
        }
