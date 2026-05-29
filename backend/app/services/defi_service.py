import time
from typing import Optional

import httpx
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
        "usdc_e": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
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
        "usdc_e": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
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
    "ethereum": {
        "rpc": "https://rpc.ankr.com/eth",
        "chain_id": 1,
        "swap_router": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "weth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "wbtc": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "usdc_decimals": 6,
        "fee": 3000,
    },
    "bsc": {
        "rpc": "https://bsc-rpc.publicnode.com",
        "chain_id": 56,
        "swap_router": "0xB971eF87ede563556b2ED4b1C0b0019111Dd85d2",
        "usdc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "weth": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
        "wbtc": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
        "usdc_decimals": 18,
        "fee": 2500,
    },
}

SYMBOL_TO_TOKEN_KEY = {
    "ETHUSDT": "weth",
    "BTCUSDT": "wbtc",
}

DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"

UNISWAP_V3_FACTORY = {
    "arbitrum": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    "optimism": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    "base":     "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
    "polygon":  "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    "ethereum": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
}

FACTORY_ABI = [
    {
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
            {"name": "fee",    "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

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


def encrypt_private_key(private_key: str) -> str:
    from app.utils.crypto import encrypt
    return encrypt(private_key)


def decrypt_private_key(encrypted: str) -> str:
    from app.utils.crypto import decrypt
    return decrypt(encrypted)


class DeFiService:
    def __init__(self, network: str = "arbitrum"):
        self.network = network
        self.net = NETWORKS.get(network) or NETWORKS["arbitrum"]
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self.net["rpc"]))

    async def get_balance(self, wallet_address: str) -> dict:
        addr = Web3.to_checksum_address(wallet_address)

        eth_wei = await self.w3.eth.get_balance(addr)
        eth_balance = eth_wei / 1e18

        # Check native USDC first, fall back to USDC.e (bridged)
        decimals = self.net["usdc_decimals"]
        active_usdc_address = self.net["usdc"]
        usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.net["usdc"]),
            abi=ERC20_ABI,
        )
        usdc_raw = await usdc_contract.functions.balanceOf(addr).call()
        usdc_balance = usdc_raw / (10 ** decimals)

        if usdc_balance < 0.01 and self.net.get("usdc_e"):
            usdc_e_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.net["usdc_e"]),
                abi=ERC20_ABI,
            )
            usdc_e_raw = await usdc_e_contract.functions.balanceOf(addr).call()
            usdc_e_balance = usdc_e_raw / (10 ** decimals)
            if usdc_e_balance > usdc_balance:
                usdc_balance = usdc_e_balance
                active_usdc_address = self.net["usdc_e"]
                logger.info("defi_using_usdc_e", wallet=wallet_address, balance=usdc_e_balance)

        return {
            "network": self.network,
            "wallet_address": wallet_address,
            "eth_balance": round(eth_balance, 6),
            "usdc_balance": round(usdc_balance, 2),
            "active_usdc_address": active_usdc_address,
            "connected": True,
        }

    async def get_token_address(self, symbol: str) -> Optional[str]:
        meta = await self.get_token_metadata(symbol, strict_network=True)
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
        "ethereum": "ethereum",
        "bsc":      "bsc",
    }

    # Fallback search order: low-gas chains first, Ethereum last
    _FALLBACK_CHAINS = ["arbitrum", "base", "bsc", "optimism", "polygon", "ethereum"]

    async def get_token_metadata(self, symbol: str, strict_network: bool = False) -> Optional[dict]:
        """Returns {address, fee, network} for a token.
        strict_network=True: only look up on self.network (no cross-chain fallback) — use for actual swaps.
        strict_network=False: fallback to other chains — use for availability checks only.
        """
        sym = symbol.upper()

        if self.network == "arbitrum" and sym in ARBITRUM_KNOWN_TOKENS:
            return {**ARBITRUM_KNOWN_TOKENS[sym], "network": "arbitrum"}

        # Separate cache keys for strict vs check to avoid cross-contamination
        strict_key = f"strict:{self.network}:{sym}"
        check_key = f"check:{self.network}:{sym}"

        if strict_network and strict_key in _dexscreener_cache:
            return _dexscreener_cache[strict_key]

        if not strict_network and check_key in _dexscreener_cache:
            return _dexscreener_cache[check_key]

        # Try primary network
        primary_chain_id = self._DEXSCREENER_CHAIN.get(self.network)
        if primary_chain_id:
            result = await self._lookup_token_on_network(sym, primary_chain_id)
            if result:
                result["network"] = self.network
                _dexscreener_cache[strict_key] = result
                _dexscreener_cache[check_key] = result
                logger.info("token_found_on_chain", symbol=sym, network=self.network, address=result["address"])
                return result

        if strict_network:
            _dexscreener_cache[strict_key] = None
            logger.info("token_not_found_strict", symbol=sym, network=self.network)
            return None

        # Fallback: other chains (only for /check endpoint, not for swaps)
        fallback_chains = [c for c in self._FALLBACK_CHAINS if c != self.network]
        for network_name in fallback_chains:
            chain_id = self._DEXSCREENER_CHAIN.get(network_name)
            if not chain_id:
                continue
            result = await self._lookup_token_on_network(sym, chain_id)
            if result:
                result["network"] = network_name
                _dexscreener_cache[check_key] = result
                logger.info("token_found_fallback_chain", symbol=sym, primary=self.network, found_on=network_name, address=result["address"])
                return result

        _dexscreener_cache[check_key] = None
        logger.info("token_not_found_any_chain", symbol=sym, primary=self.network)
        return None

    async def _detect_fee_tier(self, token_address: str, usdc_address: str) -> int:
        """Query Uniswap V3 factory to find which fee tier has a pool. Returns 3000 as fallback."""
        factory_addr = UNISWAP_V3_FACTORY.get(self.network)
        if not factory_addr:
            return 3000
        try:
            factory = self.w3.eth.contract(
                address=Web3.to_checksum_address(factory_addr),
                abi=FACTORY_ABI,
            )
            ta = Web3.to_checksum_address(token_address)
            ua = Web3.to_checksum_address(usdc_address)
            zero = "0x0000000000000000000000000000000000000000"
            for fee in (500, 3000, 10000):
                pool = await factory.functions.getPool(ta, ua, fee).call()
                if pool != zero:
                    logger.info("fee_tier_detected", token=token_address, fee=fee, pool=pool, network=self.network)
                    return fee
        except Exception as exc:
            logger.warning("fee_tier_detection_failed", token=token_address, error=str(exc))
        return 3000

    async def _lookup_token_on_network(self, symbol: str, chain_id: str) -> Optional[dict]:
        """Query DexScreener for token on given chain. Any DEX, min $1k liquidity."""
        base = symbol.replace("USDT", "").replace("USDC", "").replace("PERP", "")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(DEXSCREENER_SEARCH_URL, params={"q": base})
                if resp.status_code != 200:
                    return None
                pairs = resp.json().get("pairs") or []

            _QUOTE_PRIORITY = {"USDC": 0, "USDC.E": 1, "USDT": 2, "WETH": 3, "WBNB": 4, "ETH": 5}

            candidates = [
                p for p in pairs
                if p.get("chainId") == chain_id
                and p.get("baseToken", {}).get("symbol", "").upper() == base.upper()
                and p.get("quoteToken", {}).get("symbol", "").upper() in _QUOTE_PRIORITY
                and float((p.get("liquidity") or {}).get("usd") or 0) > 1_000
            ]

            if not candidates:
                logger.info("dexscreener_no_pair", symbol=symbol, chain=chain_id)
                return None

            candidates.sort(
                key=lambda p: (
                    _QUOTE_PRIORITY.get(p.get("quoteToken", {}).get("symbol", "").upper(), 99),
                    -float((p.get("liquidity") or {}).get("usd") or 0),
                ),
            )
            best = candidates[0]
            address = best["baseToken"]["address"]
            dex = best.get("dexId", "unknown")
            quote = best.get("quoteToken", {}).get("symbol", "")
            liquidity = float((best.get("liquidity") or {}).get("usd") or 0)
            logger.info("dexscreener_token_found", symbol=symbol, chain=chain_id, address=address, dex=dex, quote=quote, liquidity=liquidity)
            usdc_addr = self.net["usdc"]
            fee = await self._detect_fee_tier(address, usdc_addr)
            return {"address": address, "fee": fee}

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
        # Brief wait for approve only — swap nonce depends on it being mined
        try:
            await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=45)
        except Exception:
            pass  # proceed with swap even if receipt times out
        return tx_hash

    async def swap_usdc_to_token(
        self,
        private_key_encrypted: str,
        token_address: str,
        amount_usdc: float,
        slippage: float = 0.005,
        fee: int = 3000,
        usdc_address: str | None = None,
        wallet_address: str | None = None,
    ) -> dict:
        private_key = decrypt_private_key(private_key_encrypted)
        # Use explicitly-provided wallet address (from settings) — avoids mismatch if key was imported differently
        wallet_addr = Web3.to_checksum_address(wallet_address) if wallet_address else Account.from_key(private_key).address

        usdc_addr = Web3.to_checksum_address(usdc_address or self.net["usdc"])
        token_addr = Web3.to_checksum_address(token_address)
        router_addr = Web3.to_checksum_address(self.net["swap_router"])

        # Pre-flight: verify ETH balance for gas
        eth_wei = await self.w3.eth.get_balance(Web3.to_checksum_address(wallet_addr))
        eth_balance = eth_wei / 1e18
        gas_token = "BNB" if self.network == "bsc" else "MATIC" if self.network == "polygon" else "ETH"
        if eth_balance < 0.0001:
            raise ValueError(
                f"Insufficient gas on {self.network}: wallet {wallet_addr} has {eth_balance:.6f} {gas_token}. "
                f"Add {gas_token} to your wallet on {self.network} to pay for gas fees."
            )

        # Pre-flight: verify USDC balance
        usdc_contract = self.w3.eth.contract(address=usdc_addr, abi=ERC20_ABI)
        usdc_raw = await usdc_contract.functions.balanceOf(Web3.to_checksum_address(wallet_addr)).call()
        amount_in = int(amount_usdc * (10 ** self.net["usdc_decimals"]))
        if usdc_raw < amount_in:
            usdc_available = usdc_raw / (10 ** self.net["usdc_decimals"])
            raise ValueError(
                f"Wallet {wallet_addr} USDC balance {usdc_available:.4f} < required {amount_usdc:.4f}. "
                "Private key may not match the wallet address configured in settings."
            )

        nonce = await self.w3.eth.get_transaction_count(wallet_addr)
        gas_price = int((await self.w3.eth.gas_price) * 1.3)

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
            "gas": 300000,
        })
        signed = Account.sign_transaction(swap_tx, private_key)
        swap_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hex = swap_hash.hex()
        logger.info("defi_swap_buy_submitted", tx=tx_hex, amount_usdc=amount_usdc, network=self.network)
        # Return immediately after broadcast — don't block waiting for confirmation
        return {
            "direction": "buy",
            "status": "submitted",
            "tx_hash": tx_hex,
            "amount_usdc": amount_usdc,
            "network": self.network,
        }

    async def sell_all_to_usdc(
        self,
        private_key_encrypted: str,
        token_address: str,
        slippage: float = 0.005,
        fee: int = 3000,
        wallet_address: str | None = None,
    ) -> dict:
        private_key = decrypt_private_key(private_key_encrypted)
        wallet_addr = Web3.to_checksum_address(wallet_address) if wallet_address else Account.from_key(private_key).address

        token_addr = Web3.to_checksum_address(token_address)
        usdc_addr = Web3.to_checksum_address(self.net["usdc"])
        router_addr = Web3.to_checksum_address(self.net["swap_router"])

        token_balance, _ = await self.get_token_balance(wallet_addr, token_address)
        if token_balance == 0:
            return {"direction": "sell", "status": "no_balance", "message": "No token balance to sell"}

        nonce = await self.w3.eth.get_transaction_count(wallet_addr)
        gas_price = int((await self.w3.eth.gas_price) * 1.3)

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
            "gas": 300000,
        })
        signed = Account.sign_transaction(swap_tx, private_key)
        swap_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hex = swap_hash.hex()
        logger.info("defi_swap_sell_submitted", tx=tx_hex, token_balance=token_balance, network=self.network)
        # Return immediately after broadcast — don't block waiting for confirmation
        return {
            "direction": "sell",
            "status": "submitted",
            "tx_hash": tx_hex,
            "token_amount_raw": token_balance,
            "network": self.network,
        }
