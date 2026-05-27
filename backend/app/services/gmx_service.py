import base64
import hashlib
from typing import Optional

from eth_account import Account
from web3 import AsyncWeb3

from app.config import settings as app_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# GMX V2 Contracts — Arbitrum One
GMX_EXCHANGE_ROUTER = "0x7C68C7866A64FA2160F78EEaE12217FFbf871fa8"
GMX_ORDER_VAULT = "0x31eF83a530Fde1B38EE9A18093A333D8Bbbc40D5"
GMX_READER = "0x60a0fF4cDaF0f6D496d71e0bC0fFa86FE8E6B23c"
GMX_DATASTORE = "0xFD70de6b91282D8017aA4E741e9AE325CAb992d8"
ARB_RPC = "https://arb1.arbitrum.io/rpc"
USDC_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"

# Execution fee paid to GMX keeper (~0.0005 ETH, partially refunded)
EXECUTION_FEE_ETH = 0.0005

ORDER_TYPE_MARKET_INCREASE = 2
ORDER_TYPE_MARKET_DECREASE = 4

# GMX V2 markets on Arbitrum: Bybit symbol → {market_token, index_token}
# All index tokens are 18 decimals; WBTC (8 dec) excluded for simplicity
GMX_MARKETS: dict[str, dict] = {
    "ETHUSDT":  {"market": "0x70d95587d40A2caf56bd97485aB3Eec10Bee6336", "index": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"},
    "ARBUSDT":  {"market": "0xC25cEf6061Cf5dE5eb761b50E4743c1F5D7E5407", "index": "0x912CE59144191C1204E64559FE8253a0e49E6548"},
    "LINKUSDT": {"market": "0x7f1fa204bb700853D36994DA19F830b6Ad18d9a9", "index": "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4"},
    "SOLUSDT":  {"market": "0x09400D9DB990D5ed3f35D7be61DfAEB900Af03C9", "index": "0x2bcC6D6CdBbDC0a4071e48bb3B969b06B3330c07"},
    "AVAXUSDT": {"market": "0x7BbBf946883a5701350007320F525c5379B8178A", "index": "0x565609fAF65B74E7c8F31CBAA8a7409B9B6f4839"},
    "GMXUSDT":  {"market": "0x1CbBa6346F110c8A5ea739ef2d1eb182990e4EB2", "index": "0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a"},
    "OPUSDT":   {"market": "0xD9535bB5f58A1a75032416F2dFe7880C30575a41", "index": "0xaC800FD6159c2a2CB8fC31EF74621eB430287a5A"},
}

EXCHANGE_ROUTER_ABI = [
    {
        "name": "multicall",
        "type": "function",
        "inputs": [{"name": "data", "type": "bytes[]"}],
        "outputs": [{"name": "results", "type": "bytes[]"}],
        "stateMutability": "payable",
    },
    {
        "name": "sendTokens",
        "type": "function",
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "receiver", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "sendNativeToken",
        "type": "function",
        "inputs": [
            {"name": "receiver", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "createOrder",
        "type": "function",
        "inputs": [
            {
                "name": "params",
                "type": "tuple",
                "components": [
                    {
                        "name": "addresses",
                        "type": "tuple",
                        "components": [
                            {"name": "receiver", "type": "address"},
                            {"name": "callbackContract", "type": "address"},
                            {"name": "uiFeeReceiver", "type": "address"},
                            {"name": "market", "type": "address"},
                            {"name": "initialCollateralToken", "type": "address"},
                            {"name": "swapPath", "type": "address[]"},
                        ],
                    },
                    {
                        "name": "numbers",
                        "type": "tuple",
                        "components": [
                            {"name": "sizeDeltaUsd", "type": "uint256"},
                            {"name": "initialCollateralDeltaAmount", "type": "uint256"},
                            {"name": "triggerPrice", "type": "uint256"},
                            {"name": "acceptablePrice", "type": "uint256"},
                            {"name": "executionFee", "type": "uint256"},
                            {"name": "callbackGasLimit", "type": "uint256"},
                            {"name": "minOutputAmount", "type": "uint256"},
                        ],
                    },
                    {"name": "orderType", "type": "uint8"},
                    {"name": "decreasePositionSwapType", "type": "uint8"},
                    {"name": "isLong", "type": "bool"},
                    {"name": "shouldUnwrapNativeToken", "type": "bool"},
                    {"name": "referralCode", "type": "bytes32"},
                ],
            }
        ],
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "nonpayable",
    },
]

ERC20_ABI = [
    {
        "name": "approve",
        "type": "function",
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "name": "allowance",
        "type": "function",
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "balanceOf",
        "type": "function",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
]

READER_ABI = [
    {
        "name": "getAccountPositions",
        "type": "function",
        "inputs": [
            {"name": "dataStore", "type": "address"},
            {"name": "account", "type": "address"},
            {"name": "start", "type": "uint256"},
            {"name": "end", "type": "uint256"},
        ],
        "outputs": [
            {
                "name": "",
                "type": "tuple[]",
                "components": [
                    {
                        "name": "addresses",
                        "type": "tuple",
                        "components": [
                            {"name": "account", "type": "address"},
                            {"name": "market", "type": "address"},
                            {"name": "collateralToken", "type": "address"},
                        ],
                    },
                    {
                        "name": "numbers",
                        "type": "tuple",
                        "components": [
                            {"name": "sizeInUsd", "type": "uint256"},
                            {"name": "sizeInTokens", "type": "uint256"},
                            {"name": "collateralAmount", "type": "uint256"},
                            {"name": "borrowingFactor", "type": "uint256"},
                            {"name": "fundingFeeAmountPerSize", "type": "uint256"},
                            {"name": "longTokenClaimableFundingAmountPerSize", "type": "uint256"},
                            {"name": "shortTokenClaimableFundingAmountPerSize", "type": "uint256"},
                            {"name": "increasedAtBlock", "type": "uint256"},
                            {"name": "decreasedAtBlock", "type": "uint256"},
                            {"name": "increasedAtTime", "type": "uint256"},
                            {"name": "decreasedAtTime", "type": "uint256"},
                        ],
                    },
                    {
                        "name": "flags",
                        "type": "tuple",
                        "components": [{"name": "isLong", "type": "bool"}],
                    },
                ],
            }
        ],
        "stateMutability": "view",
    },
]


class GMXService:
    def __init__(self):
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(ARB_RPC))
        self.router = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(GMX_EXCHANGE_ROUTER),
            abi=EXCHANGE_ROUTER_ABI,
        )
        self.reader = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(GMX_READER),
            abi=READER_ABI,
        )
        self._fernet = None

    def _get_fernet(self):
        if self._fernet is None:
            from cryptography.fernet import Fernet
            key = hashlib.sha256(app_settings.SECRET_KEY.encode()).digest()
            self._fernet = Fernet(base64.urlsafe_b64encode(key))
        return self._fernet

    def _decrypt_key(self, encrypted: str) -> str:
        return self._get_fernet().decrypt(encrypted.encode()).decode()

    @staticmethod
    def get_available_markets() -> list[dict]:
        return [
            {"symbol": sym, "market": info["market"], "index_token": info["index"]}
            for sym, info in GMX_MARKETS.items()
        ]

    @staticmethod
    def supports_symbol(symbol: str) -> bool:
        return symbol.upper() in GMX_MARKETS

    async def get_positions(self, wallet_address: str) -> list[dict]:
        try:
            raw = await self.reader.functions.getAccountPositions(
                AsyncWeb3.to_checksum_address(GMX_DATASTORE),
                AsyncWeb3.to_checksum_address(wallet_address),
                0,
                20,
            ).call()
        except Exception as exc:
            logger.error("gmx_get_positions_failed", wallet=wallet_address, error=str(exc))
            return []

        market_to_symbol = {v["market"].lower(): k for k, v in GMX_MARKETS.items()}
        positions = []
        for pos in raw:
            market_addr = pos[0][1].lower()
            size_usd = pos[1][0]
            collateral = pos[1][2]
            is_long = pos[2][0]
            if size_usd == 0:
                continue
            positions.append({
                "symbol": market_to_symbol.get(market_addr, market_addr),
                "market": market_addr,
                "size_usd": size_usd / 1e30,
                "collateral_usdc": collateral / 1e6,
                "is_long": is_long,
                "direction": "LONG" if is_long else "SHORT",
            })
        return positions

    async def _ensure_usdc_approved(self, account, usdc_contract, router_addr: str, collateral_amount: int) -> int:
        """Approve USDC to router if needed. Returns new nonce offset."""
        wallet = account.address
        nonce = await self.w3.eth.get_transaction_count(wallet)
        gas_price = await self.w3.eth.gas_price

        allowance = await usdc_contract.functions.allowance(wallet, router_addr).call()
        if allowance >= collateral_amount:
            return nonce

        approve_tx = await usdc_contract.functions.approve(
            router_addr, 2**256 - 1
        ).build_transaction({"from": wallet, "nonce": nonce, "gasPrice": gas_price, "gas": 100_000})
        signed = account.sign_transaction(approve_tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        logger.info("gmx_usdc_approved", wallet=wallet)
        return nonce + 1

    def _acceptable_price(self, current_price: float, is_long: bool, slippage: float) -> int:
        if current_price <= 0:
            return 0
        if is_long:
            return int(current_price * (1 + slippage) * 1e12)
        return int(current_price * (1 - slippage) * 1e12)

    async def open_position(
        self,
        private_key_encrypted: str,
        symbol: str,
        is_long: bool,
        collateral_usdc: float,
        leverage: float = 2.0,
        current_price: float = 0.0,
        slippage: float = 0.01,
    ) -> dict:
        symbol = symbol.upper()
        if symbol not in GMX_MARKETS:
            return {"status": "error", "error": f"{symbol} not in GMX markets"}

        private_key = self._decrypt_key(private_key_encrypted)
        account = Account.from_key(private_key)
        wallet = account.address
        router_addr = AsyncWeb3.to_checksum_address(GMX_EXCHANGE_ROUTER)
        order_vault = AsyncWeb3.to_checksum_address(GMX_ORDER_VAULT)
        usdc_addr = AsyncWeb3.to_checksum_address(USDC_ADDRESS)
        market_addr = AsyncWeb3.to_checksum_address(GMX_MARKETS[symbol]["market"])

        collateral_amount = int(collateral_usdc * 1e6)
        size_delta_usd = int(collateral_usdc * leverage * 1e30)
        exec_fee_wei = int(EXECUTION_FEE_ETH * 1e18)

        usdc_contract = self.w3.eth.contract(address=usdc_addr, abi=ERC20_ABI)
        usdc_balance = await usdc_contract.functions.balanceOf(wallet).call()
        if usdc_balance < collateral_amount:
            return {"status": "error", "error": f"Insufficient USDC: {usdc_balance/1e6:.2f} < {collateral_usdc:.2f}"}

        eth_balance = await self.w3.eth.get_balance(wallet)
        if eth_balance < exec_fee_wei * 3:
            return {"status": "error", "error": f"Insufficient ETH for execution fee: {eth_balance/1e18:.6f}"}

        nonce = await self._ensure_usdc_approved(account, usdc_contract, router_addr, collateral_amount)
        gas_price = await self.w3.eth.gas_price
        acceptable_price = self._acceptable_price(current_price, is_long, slippage)

        order_params = (
            (wallet, "0x0000000000000000000000000000000000000000",
             "0x0000000000000000000000000000000000000000",
             market_addr, usdc_addr, []),
            (size_delta_usd, collateral_amount, 0, acceptable_price, exec_fee_wei, 0, 0),
            ORDER_TYPE_MARKET_INCREASE, 0, is_long, False, b"\x00" * 32,
        )

        send_tokens = self.router.encode_abi("sendTokens", args=[usdc_addr, order_vault, collateral_amount])
        send_native = self.router.encode_abi("sendNativeToken", args=[order_vault, exec_fee_wei])
        create_order = self.router.encode_abi("createOrder", args=[order_params])

        multicall_tx = await self.router.functions.multicall(
            [send_tokens, send_native, create_order]
        ).build_transaction({
            "from": wallet, "nonce": nonce, "gasPrice": gas_price,
            "gas": 1_500_000, "value": exec_fee_wei,
        })

        signed = account.sign_transaction(multicall_tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt["status"] != 1:
            return {"status": "error", "error": "Transaction reverted", "tx_hash": tx_hash.hex()}

        return {
            "status": "success",
            "tx_hash": tx_hash.hex(),
            "symbol": symbol,
            "direction": "LONG" if is_long else "SHORT",
            "collateral_usdc": collateral_usdc,
            "size_usd": round(collateral_usdc * leverage, 2),
            "leverage": leverage,
            "entry_price": current_price,
            "gas_used": receipt["gasUsed"],
        }

    async def close_position(
        self,
        private_key_encrypted: str,
        symbol: str,
        is_long: bool,
        size_usd: float,
        current_price: float = 0.0,
        slippage: float = 0.01,
    ) -> dict:
        symbol = symbol.upper()
        if symbol not in GMX_MARKETS:
            return {"status": "error", "error": f"{symbol} not in GMX markets"}

        private_key = self._decrypt_key(private_key_encrypted)
        account = Account.from_key(private_key)
        wallet = account.address
        order_vault = AsyncWeb3.to_checksum_address(GMX_ORDER_VAULT)
        usdc_addr = AsyncWeb3.to_checksum_address(USDC_ADDRESS)
        market_addr = AsyncWeb3.to_checksum_address(GMX_MARKETS[symbol]["market"])

        size_delta_usd = int(size_usd * 1e30)
        exec_fee_wei = int(EXECUTION_FEE_ETH * 1e18)

        eth_balance = await self.w3.eth.get_balance(wallet)
        if eth_balance < exec_fee_wei * 3:
            return {"status": "error", "error": f"Insufficient ETH for close execution fee"}

        nonce = await self.w3.eth.get_transaction_count(wallet)
        gas_price = await self.w3.eth.gas_price
        # For decrease: acceptable_price is inverted (long close = min acceptable, short close = max acceptable)
        acceptable_price = self._acceptable_price(current_price, not is_long, slippage)

        order_params = (
            (wallet, "0x0000000000000000000000000000000000000000",
             "0x0000000000000000000000000000000000000000",
             market_addr, usdc_addr, []),
            (size_delta_usd, 0, 0, acceptable_price, exec_fee_wei, 0, 0),
            ORDER_TYPE_MARKET_DECREASE, 0, is_long, False, b"\x00" * 32,
        )

        send_native = self.router.encode_abi("sendNativeToken", args=[order_vault, exec_fee_wei])
        create_order = self.router.encode_abi("createOrder", args=[order_params])

        multicall_tx = await self.router.functions.multicall(
            [send_native, create_order]
        ).build_transaction({
            "from": wallet, "nonce": nonce, "gasPrice": gas_price,
            "gas": 1_200_000, "value": exec_fee_wei,
        })

        signed = account.sign_transaction(multicall_tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt["status"] != 1:
            return {"status": "error", "error": "Transaction reverted", "tx_hash": tx_hash.hex()}

        return {
            "status": "success",
            "tx_hash": tx_hash.hex(),
            "symbol": symbol,
            "direction": "CLOSE_LONG" if is_long else "CLOSE_SHORT",
            "size_usd": size_usd,
            "gas_used": receipt["gasUsed"],
        }
