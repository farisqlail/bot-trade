import base64
import hashlib
import time
from typing import Optional

import httpx
from cryptography.fernet import Fernet
from eth_account import Account
from web3 import AsyncWeb3, Web3

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Arbitrum token registry: symbol (Bybit) → {address, fee_tier}
# fee_tier: Uniswap V3 pool fee in bps*100 (500=0.05%, 3000=0.3%, 10000=1%)
ARBITRUM_KNOWN_TOKENS: dict[str, dict] = {
    "ETHUSDT":    {"address": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", "fee": 500},
    "BTCUSDT":    {"address": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f", "fee": 500},
    "WBTCUSDT":   {"address": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f", "fee": 500},
    "ARBUSDT":    {"address": "0x912CE59144191C1204E64559FE8253a0e49E6548", "fee": 500},
    "GMXUSDT":    {"address": "0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a", "fee": 3000},
    "PENDLEUSDT": {"address": "0x0c880f6761F1af8d9Aa9C466984b80DAb9a8c9e8", "fee": 3000},
    "LINKUSDT":   {"address": "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4", "fee": 3000},
    "CRVUSDT":    {"address": "0x11cDb42B0EB46D95f990BeDD4695A6e3fA034978", "fee": 3000},
    "UNIUSDT":    {"address": "0xFa7F8980b0f1E64A2062791cc3b0871572f1F7f0", "fee": 3000},
    "MAGICUSDT":  {"address": "0x539bdE0d7Dbd336b79148AA742883198BBF60342", "fee": 3000},
    "DPXUSDT":    {"address": "0x6C2C06790b3E3E3c38e12Ee22F8183b37a13EE55", "fee": 10000},
    "GNSUSDT":    {"address": "0x18c11FD286C5EC11c3b683Caa813B77f5163A122", "fee": 3000},
    "STGUSDT":    {"address": "0x6694340fc020c5E6B96567843da2df01b2CE1eb6", "fee": 3000},
    "RDNTUSDT":   {"address": "0x3082CC23568eA640225c2467653dB90e9250AaA0", "fee": 3000},
    "SUSHIUSDT":  {"address": "0xd4d42F0b6DEF4CE0383636770eF773390d85c61A", "fee": 3000},
    "AAVEUSDT":   {"address": "0xba5DdD1f9d7F570dc94a51479a000E3BCE967196", "fee": 3000},
    "LDOUSDT":    {"address": "0x13Ad51ed4F1B7e9Dc168d8a00cB3f4dDD85EfA60", "fee": 3000},
    "BALUSDT":    {"address": "0x040d1EdC9569d4Bab2D15287Dc5A4F10F56a56B8", "fee": 3000},
    "1INCHUSDT":  {"address": "0x6314C31A7a1652cE482cffe247E9CB7c3f4BB9aF", "fee": 3000},
    "SNXUSDT":    {"address": "0xcBA56Cd8216FCBBF3fA6DF6b9306C0e7CEB01E06", "fee": 3000},
    "YFIUSDT":    {"address": "0x82e3A8F066a6989666b031d916c43672085b1582", "fee": 10000},
    "COMPUSDT":   {"address": "0x354A6dA3fcde098F8389cad84b0182725c6C91dE", "fee": 3000},
    "OPUSDT":     {"address": "0xaC800FD6159c2a2CB8fC31EF74621eB430287a5A", "fee": 3000},
}

# In-memory cache for DexScreener lookups: symbol → {address, fee} | None
_dexscreener_cache: dict[str, dict | None] = {}

NETWORKS = {
    "arbitrum": {
        "rpc": "https://arb1.arbitrum.io/rpc",
        "chain_id": 42161,
        "swap_router": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "usdc": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "weth": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "wbtc": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
        "usdc_decimals": 6,
        "fee": 500,
    },
    "optimism": {
        "rpc": "https://mainnet.optimism.io",
        "chain_id": 10,
        "swap_router": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "usdc": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        "weth": "0x4200000000000000000000000000000000000006",
        "wbtc": "0x68f180fcCe6836688e9084f035309E29Bf0A2095",
        "usdc_decimals": 6,
        "fee": 500,
    },
    "base": {
        "rpc": "https://mainnet.base.org",
        "chain_id": 8453,
        "swap_router": "0x2626664c2603336E57B271c5C0b26F421741e481",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "weth": "0x4200000000000000000000000000000000000006",
        "wbtc": "0x0555E30da8f98308EdB960aa94C0Db47230d2B9c",
        "usdc_decimals": 6,
        "fee": 500,
    },
    "polygon": {
        "rpc": "https://polygon-rpc.com",
        "chain_id": 137,
        "swap_router": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "usdc": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "weth": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "wbtc": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        "usdc_decimals": 6,
        "fee": 500,
    },
}

SYMBOL_TO_TOKEN_KEY = {
    "ETHUSDT": "weth",
    "BTCUSDT": "wbtc",
}

DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"

ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# SwapRouter02 ABI — no deadline in struct (handled by contract internally)
SWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "recipient", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMinimum", "type": "uint256"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]


def _get_fernet() -> Fernet:
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_private_key(private_key: str) -> str:
    return _get_fernet().encrypt(private_key.encode()).decode()


def decrypt_private_key(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


class DeFiService:
    def __init__(self, network: str = "arbitrum"):
        self.network = network
        self.net = NETWORKS.get(network) or NETWORKS["arbitrum"]
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self.net["rpc"]))

    async def get_balance(self, wallet_address: str) -> dict:
        addr = Web3.to_checksum_address(wallet_address)

        eth_wei = await self.w3.eth.get_balance(addr)
        eth_balance = eth_wei / 1e18

        usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.net["usdc"]),
            abi=ERC20_ABI,
        )
        usdc_raw = await usdc_contract.functions.balanceOf(addr).call()
        usdc_balance = usdc_raw / (10 ** self.net["usdc_decimals"])

        return {
            "network": self.network,
            "wallet_address": wallet_address,
            "eth_balance": round(eth_balance, 6),
            "usdc_balance": round(usdc_balance, 2),
            "connected": True,
        }

    async def get_token_address(self, symbol: str) -> Optional[str]:
        meta = await self.get_token_metadata(symbol)
        return meta["address"] if meta else None

    def get_token_fee(self, symbol: str) -> int:
        sym = symbol.upper()
        if self.network == "arbitrum" and sym in ARBITRUM_KNOWN_TOKENS:
            return ARBITRUM_KNOWN_TOKENS[sym]["fee"]
        cached = _dexscreener_cache.get(f"{self.network}:{sym}")
        if cached:
            return cached.get("fee", self.net["fee"])
        return self.net["fee"]

    # DexScreener chain ID per network name
    _DEXSCREENER_CHAIN: dict[str, str] = {
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "base":     "base",
        "polygon":  "polygon",
    }

    async def get_token_metadata(self, symbol: str) -> Optional[dict]:
        """Returns {address, fee} for a token on this network. Checks static map first, then DexScreener."""
        sym = symbol.upper()

        if self.network == "arbitrum" and sym in ARBITRUM_KNOWN_TOKENS:
            return ARBITRUM_KNOWN_TOKENS[sym]

        cache_key = f"{self.network}:{sym}"
        if cache_key in _dexscreener_cache:
            return _dexscreener_cache[cache_key]

        # Try DexScreener for all supported networks
        chain_id = self._DEXSCREENER_CHAIN.get(self.network)
        if chain_id:
            result = await self._lookup_token_on_network(sym, chain_id)
            _dexscreener_cache[cache_key] = result
            return result

        # Legacy fallback for unknown networks
        token_key = SYMBOL_TO_TOKEN_KEY.get(sym)
        if not token_key:
            return None
        addr = self.net.get(token_key)
        return {"address": addr, "fee": self.net["fee"]} if addr else None

    async def _lookup_token_on_network(self, symbol: str, chain_id: str) -> Optional[dict]:
        """Query DexScreener for token on given chain, Uniswap V3, USDC pair, >$50k liquidity."""
        base = symbol.replace("USDT", "").replace("USDC", "")
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(DEXSCREENER_SEARCH_URL, params={"q": base})
                if resp.status_code != 200:
                    return None
                pairs = resp.json().get("pairs") or []

            candidates = [
                p for p in pairs
                if p.get("chainId") == chain_id
                and p.get("dexId") == "uniswap-v3"
                and p.get("baseToken", {}).get("symbol", "").upper() == base.upper()
                and p.get("quoteToken", {}).get("symbol", "").upper() in ("USDC", "USDC.E")
                and float((p.get("liquidity") or {}).get("usd") or 0) > 50_000
            ]

            if not candidates:
                logger.info("dexscreener_no_pair", symbol=symbol, chain=chain_id)
                return None

            candidates.sort(
                key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0),
                reverse=True,
            )
            best = candidates[0]
            address = best["baseToken"]["address"]
            logger.info("dexscreener_token_found", symbol=symbol, chain=chain_id, address=address)
            return {"address": address, "fee": 3000}

        except Exception as exc:
            logger.warning("dexscreener_lookup_failed", symbol=symbol, chain=chain_id, error=str(exc))
            return None

    async def get_token_balance(self, wallet_address: str, token_address: str) -> tuple[int, int]:
        """Returns (raw_balance, decimals)."""
        addr = Web3.to_checksum_address(wallet_address)
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        raw = await contract.functions.balanceOf(addr).call()
        decimals = await contract.functions.decimals().call()
        return raw, decimals

    async def _approve(self, private_key: str, token_address: str, spender: str, amount: int, nonce: int, gas_price: int) -> bytes:
        wallet_addr = Account.from_key(private_key).address
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        tx = await contract.functions.approve(
            Web3.to_checksum_address(spender), amount
        ).build_transaction({
            "from": wallet_addr,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": self.net["chain_id"],
        })
        gas = await self.w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas * 1.3)
        signed = Account.sign_transaction(tx, private_key)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        return tx_hash

    async def swap_usdc_to_token(
        self,
        private_key_encrypted: str,
        token_address: str,
        amount_usdc: float,
        slippage: float = 0.005,
        fee: int = 3000,
    ) -> dict:
        private_key = decrypt_private_key(private_key_encrypted)
        account = Account.from_key(private_key)
        wallet_addr = account.address

        usdc_addr = Web3.to_checksum_address(self.net["usdc"])
        token_addr = Web3.to_checksum_address(token_address)
        router_addr = Web3.to_checksum_address(self.net["swap_router"])

        amount_in = int(amount_usdc * (10 ** self.net["usdc_decimals"]))
        nonce = await self.w3.eth.get_transaction_count(wallet_addr)
        gas_price = await self.w3.eth.gas_price

        await self._approve(private_key, usdc_addr, router_addr, amount_in, nonce, gas_price)

        router = self.w3.eth.contract(address=router_addr, abi=SWAP_ROUTER_ABI)
        swap_tx = await router.functions.exactInputSingle({
            "tokenIn": usdc_addr,
            "tokenOut": token_addr,
            "fee": fee,
            "recipient": wallet_addr,
            "amountIn": amount_in,
            "amountOutMinimum": 0,
            "sqrtPriceLimitX96": 0,
        }).build_transaction({
            "from": wallet_addr,
            "nonce": nonce + 1,
            "gasPrice": gas_price,
            "chainId": self.net["chain_id"],
        })
        gas = await self.w3.eth.estimate_gas(swap_tx)
        swap_tx["gas"] = int(gas * 1.3)
        signed = Account.sign_transaction(swap_tx, private_key)
        swap_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self.w3.eth.wait_for_transaction_receipt(swap_hash, timeout=120)

        logger.info("defi_swap_buy", tx=swap_hash.hex(), amount_usdc=amount_usdc, status=receipt.status)
        return {
            "direction": "buy",
            "status": "success" if receipt.status == 1 else "failed",
            "tx_hash": swap_hash.hex(),
            "amount_usdc": amount_usdc,
            "gas_used": receipt.gasUsed,
            "network": self.network,
        }

    async def sell_all_to_usdc(
        self,
        private_key_encrypted: str,
        token_address: str,
        slippage: float = 0.005,
        fee: int = 3000,
    ) -> dict:
        private_key = decrypt_private_key(private_key_encrypted)
        account = Account.from_key(private_key)
        wallet_addr = account.address

        token_addr = Web3.to_checksum_address(token_address)
        usdc_addr = Web3.to_checksum_address(self.net["usdc"])
        router_addr = Web3.to_checksum_address(self.net["swap_router"])

        token_balance, _ = await self.get_token_balance(wallet_addr, token_address)
        if token_balance == 0:
            return {"direction": "sell", "status": "no_balance", "message": "No token balance to sell"}

        nonce = await self.w3.eth.get_transaction_count(wallet_addr)
        gas_price = await self.w3.eth.gas_price

        await self._approve(private_key, token_addr, router_addr, token_balance, nonce, gas_price)

        router = self.w3.eth.contract(address=router_addr, abi=SWAP_ROUTER_ABI)
        swap_tx = await router.functions.exactInputSingle({
            "tokenIn": token_addr,
            "tokenOut": usdc_addr,
            "fee": fee,
            "recipient": wallet_addr,
            "amountIn": token_balance,
            "amountOutMinimum": 0,
            "sqrtPriceLimitX96": 0,
        }).build_transaction({
            "from": wallet_addr,
            "nonce": nonce + 1,
            "gasPrice": gas_price,
            "chainId": self.net["chain_id"],
        })
        gas = await self.w3.eth.estimate_gas(swap_tx)
        swap_tx["gas"] = int(gas * 1.3)
        signed = Account.sign_transaction(swap_tx, private_key)
        swap_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self.w3.eth.wait_for_transaction_receipt(swap_hash, timeout=120)

        logger.info("defi_swap_sell", tx=swap_hash.hex(), token_balance=token_balance, status=receipt.status)
        return {
            "direction": "sell",
            "status": "success" if receipt.status == 1 else "failed",
            "tx_hash": swap_hash.hex(),
            "token_amount_raw": token_balance,
            "gas_used": receipt.gasUsed,
            "network": self.network,
        }
