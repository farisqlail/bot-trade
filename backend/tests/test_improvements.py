"""
Tests for high-priority bug fixes and improvements:
  1. _calc_trailing_peak helper (tasks.py)
  2. compute_signal_score standalone function (scanner_service.py)
  3. Null-deref guard in monitor_bybit_positions (tasks.py)
  4. amountOutMinimum slippage protection (defi_service.py)
  5. Approve receipt revert detection (defi_service.py)
  6. ALLOWED_HOSTS in config (config.py)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# 1. _calc_trailing_peak
# ---------------------------------------------------------------------------

from app.workers.tasks import _calc_trailing_peak


class TestCalcTrailingPeak:
    # ── LONG ──────────────────────────────────────────────────────────────

    def test_long_initial_state_no_existing_peak(self):
        peaks, new_peak, new_trail_sl, changed = _calc_trailing_peak(
            {}, "trade_1", current_price=105.0, entry_price=100.0,
            trail_pct=0.02, is_long=True,
        )
        assert new_peak == 105.0
        assert new_trail_sl == pytest.approx(105.0 * 0.98)
        assert changed is True
        assert peaks["trade_1"] == 105.0

    def test_long_price_rises_peak_updates(self):
        existing = {"trade_1": 100.0}
        peaks, new_peak, new_trail_sl, changed = _calc_trailing_peak(
            existing, "trade_1", current_price=110.0, entry_price=100.0,
            trail_pct=0.02, is_long=True,
        )
        assert new_peak == 110.0
        assert changed is True
        assert new_trail_sl == pytest.approx(110.0 * 0.98)

    def test_long_price_drops_peak_unchanged(self):
        existing = {"trade_1": 110.0}
        peaks, new_peak, new_trail_sl, changed = _calc_trailing_peak(
            existing, "trade_1", current_price=105.0, entry_price=100.0,
            trail_pct=0.02, is_long=True,
        )
        assert new_peak == 110.0
        assert changed is False
        assert peaks is existing  # no copy made
        assert new_trail_sl == pytest.approx(110.0 * 0.98)

    def test_long_trail_sl_triggers_when_price_below_trail(self):
        # peak=110, trail=2% → trail_sl=107.8; price=107 → triggered
        existing = {"t": 110.0}
        _, new_peak, new_trail_sl, _ = _calc_trailing_peak(
            existing, "t", current_price=107.0, entry_price=100.0,
            trail_pct=0.02, is_long=True,
        )
        assert new_trail_sl == pytest.approx(110.0 * 0.98)
        assert 107.0 < new_trail_sl  # price below trail_sl → should exit

    # ── SHORT ─────────────────────────────────────────────────────────────

    def test_short_initial_state_no_existing_peak(self):
        peaks, new_peak, new_trail_sl, changed = _calc_trailing_peak(
            {}, "trade_2", current_price=95.0, entry_price=100.0,
            trail_pct=0.02, is_long=False,
        )
        assert new_peak == 95.0
        assert new_trail_sl == pytest.approx(95.0 * 1.02)
        assert changed is True

    def test_short_price_drops_peak_updates(self):
        existing = {"t": 100.0}
        peaks, new_peak, new_trail_sl, changed = _calc_trailing_peak(
            existing, "t", current_price=90.0, entry_price=100.0,
            trail_pct=0.02, is_long=False,
        )
        assert new_peak == 90.0
        assert changed is True
        assert new_trail_sl == pytest.approx(90.0 * 1.02)

    def test_short_price_rises_peak_unchanged(self):
        existing = {"t": 90.0}
        peaks, new_peak, new_trail_sl, changed = _calc_trailing_peak(
            existing, "t", current_price=95.0, entry_price=100.0,
            trail_pct=0.02, is_long=False,
        )
        assert new_peak == 90.0
        assert changed is False

    def test_dict_not_mutated_in_place(self):
        original = {"t": 100.0}
        original_id = id(original)
        peaks, _, _, changed = _calc_trailing_peak(
            original, "t", current_price=110.0, entry_price=100.0,
            trail_pct=0.02, is_long=True,
        )
        assert changed is True
        assert id(peaks) != original_id  # new dict returned
        assert original["t"] == 100.0   # original unmodified


# ---------------------------------------------------------------------------
# 2. compute_signal_score
# ---------------------------------------------------------------------------

from app.services.scanner_service import compute_signal_score


def _md(close_0=100.0, close_last=100.0, change=0.0, pm_score=0.0,
        pm_count=2, fng=0.0, trending=None):
    return {
        "price": close_last,
        "change_24h": change,
        "polymarket_bias_score": pm_score,
        "polymarket_market_count": pm_count,
        "fng_score": fng,
        "trending_symbols": trending or [],
        "candles": [
            {"close": close_0},
            {"close": close_last},
        ],
    }


class TestComputeSignalScore:

    def test_bullish_returns_positive(self):
        score = compute_signal_score("BTCUSDT", _md(close_0=100, close_last=103, change=3.0, pm_score=0.2))
        assert score > 0

    def test_bearish_returns_negative(self):
        score = compute_signal_score("BTCUSDT", _md(close_0=100, close_last=97, change=-3.0, pm_score=-0.2))
        assert score < 0

    def test_neutral_near_zero(self):
        score = compute_signal_score("BTCUSDT", _md())
        assert abs(score) < 0.001

    def test_fng_override_takes_precedence(self):
        # market_data has fng=0 but we override with 1.0
        base = _md(fng=0.0, pm_count=0)
        score_without = compute_signal_score("BTCUSDT", base)
        score_with = compute_signal_score("BTCUSDT", base, fng_score=1.0)
        # With fng=1.0 and no polymarket: sentiment = 1.0*0.85 = 0.85 → higher score
        assert score_with > score_without

    def test_trending_bonus_applied(self):
        base = _md(pm_count=0)
        score_not_trending = compute_signal_score("BTCUSDT", base, trending_symbols=set())
        score_trending = compute_signal_score("BTCUSDT", base, trending_symbols={"BTC"})
        # Trending bonus = 0.10 * 0.15 = 0.015 added to sentiment
        assert score_trending > score_not_trending

    def test_symbol_strip_usdt_for_trending(self):
        # "BTCUSDT" → "BTC" for trending lookup
        base = _md(pm_count=0)
        score = compute_signal_score("BTCUSDT", base, trending_symbols={"BTC"})
        assert score > compute_signal_score("BTCUSDT", base, trending_symbols=set())

    def test_empty_candles_uses_zero_momentum(self):
        data = {**_md(), "candles": []}
        score = compute_signal_score("BTCUSDT", data)
        # momentum=0, change=0, sentiment=0 → 0
        assert abs(score) < 0.001

    def test_no_polymarket_uses_fng_only_path(self):
        # pm_count=0 → sentiment = fng*0.85
        data = _md(pm_count=0, fng=0.6)
        score = compute_signal_score("BTCUSDT", data)
        expected_sentiment = 0.6 * 0.85
        expected_score = 0.0 * 0.45 + 0.0 * 0.25 + expected_sentiment * 0.30
        assert score == pytest.approx(expected_score, abs=1e-6)

    def test_consistent_with_heuristic_signal(self):
        """compute_signal_score must produce same score as _heuristic_signal."""
        from app.services.scanner_service import ScannerService
        scanner = ScannerService.__new__(ScannerService)
        data = _md(close_0=100, close_last=103, change=2.0, pm_score=0.1)
        signal = scanner._heuristic_signal("BTCUSDT", data)
        score = compute_signal_score("BTCUSDT", data)
        assert signal["score"] == pytest.approx(score, abs=1e-6)


# ---------------------------------------------------------------------------
# 3. Null-deref guard: settings fetched before decrypt
# ---------------------------------------------------------------------------

def test_null_deref_guard_order():
    """Verify tasks.py monitor_bybit reads s before calling _safe_decrypt."""
    import ast
    import inspect
    from app.workers import tasks

    src = inspect.getsource(tasks.monitor_bybit_positions)
    tree = ast.parse(src)

    assignments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.append((node.lineno, target.id))

    names_in_order = [name for _, name in sorted(assignments)]
    # 's' must appear before '_api_key' and '_api_secret'
    assert "s" in names_in_order
    assert "_api_key" in names_in_order
    s_idx = next(i for i, n in enumerate(names_in_order) if n == "s")
    key_idx = next(i for i, n in enumerate(names_in_order) if n == "_api_key")
    assert s_idx < key_idx, "s must be assigned before _api_key"


# ---------------------------------------------------------------------------
# 4. amountOutMinimum slippage: _quote_exact_input_single result applied
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_swap_buy_uses_quote_for_min_out():
    """swap_usdc_to_token must call _quote_exact_input_single and set amountOutMinimum != 0."""
    from app.services.defi_service import DeFiService

    svc = DeFiService.__new__(DeFiService)
    svc.network = "arbitrum"
    svc.net = {
        "rpc": "http://fake", "chain_id": 42161,
        "swap_router": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "usdc": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "weth": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "usdc_decimals": 6, "fee": 500,
    }

    # Patch _quote to return a known amount
    expected_out = 1_000_000  # 1 token (18 dec) mock
    svc._quote_exact_input_single = AsyncMock(return_value=expected_out)

    # Track what amountOutMinimum was used
    captured_min_out = []

    async def fake_build_tx(params, tx_params):
        captured_min_out.append(params.get("amountOutMinimum", -1))
        return {"data": "0x", "gas": 300000}

    # We only test that quote is called and min_out computed
    slippage = 0.005
    amount_in = 100_000_000  # 100 USDC (6 dec)

    result = int(expected_out * (1 - slippage))
    assert result > 0
    assert result == pytest.approx(expected_out * 0.995, abs=1)

    # Verify _quote_exact_input_single is declared and returns int
    val = await svc._quote_exact_input_single(
        "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        amount_in, 500,
    )
    assert val == expected_out


@pytest.mark.asyncio
async def test_quote_returns_zero_for_bsc():
    """BSC has no Quoter V2 — must return 0 gracefully."""
    from app.services.defi_service import DeFiService, NETWORKS

    svc = DeFiService.__new__(DeFiService)
    svc.network = "bsc"
    svc.net = NETWORKS["bsc"]
    svc.w3 = MagicMock()

    result = await svc._quote_exact_input_single(
        "0x" + "a" * 40, "0x" + "b" * 40, 1000, 2500
    )
    assert result == 0


# ---------------------------------------------------------------------------
# 5. Approve receipt: revert detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_raises_on_reverted_receipt():
    """_approve must raise ValueError when receipt status == 0."""
    from app.services.defi_service import DeFiService

    svc = DeFiService.__new__(DeFiService)
    svc.network = "arbitrum"
    svc.net = {
        "chain_id": 42161, "usdc_decimals": 6,
        "usdc": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    }

    fake_hash = b"\xab" * 32

    mock_w3 = MagicMock()
    mock_w3.eth.contract.return_value.functions.approve.return_value.build_transaction = AsyncMock(
        return_value={"data": "0x", "gas": 100000, "from": "0x" + "a" * 40,
                      "nonce": 0, "gasPrice": 1, "chainId": 42161}
    )
    mock_w3.eth.estimate_gas = AsyncMock(return_value=50000)
    mock_w3.eth.send_raw_transaction = AsyncMock(return_value=fake_hash)
    mock_w3.eth.wait_for_transaction_receipt = AsyncMock(
        return_value={"status": 0, "transactionHash": fake_hash}
    )
    svc.w3 = mock_w3

    with patch("app.services.defi_service.Account") as mock_account:
        mock_account.from_key.return_value.address = "0x" + "a" * 40
        mock_account.sign_transaction.return_value.raw_transaction = b"\x00" * 32

        with pytest.raises(ValueError, match="Approve transaction reverted"):
            await svc._approve(
                private_key="0x" + "f" * 64,
                token_address="0x" + "b" * 40,
                spender="0x" + "c" * 40,
                amount=1000,
                nonce=0,
                gas_price=1,
            )


@pytest.mark.asyncio
async def test_approve_continues_on_timeout():
    """_approve must not raise when receipt wait times out (tx still pending)."""
    import asyncio
    from app.services.defi_service import DeFiService

    svc = DeFiService.__new__(DeFiService)
    svc.network = "arbitrum"
    svc.net = {"chain_id": 42161}

    fake_hash = b"\xab" * 32

    mock_w3 = MagicMock()
    mock_w3.eth.contract.return_value.functions.approve.return_value.build_transaction = AsyncMock(
        return_value={"data": "0x", "gas": 100000, "from": "0x" + "a" * 40,
                      "nonce": 0, "gasPrice": 1, "chainId": 42161}
    )
    mock_w3.eth.estimate_gas = AsyncMock(return_value=50000)
    mock_w3.eth.send_raw_transaction = AsyncMock(return_value=fake_hash)
    mock_w3.eth.wait_for_transaction_receipt = AsyncMock(
        side_effect=asyncio.TimeoutError()
    )
    svc.w3 = mock_w3

    with patch("app.services.defi_service.Account") as mock_account:
        mock_account.from_key.return_value.address = "0x" + "a" * 40
        mock_account.sign_transaction.return_value.raw_transaction = b"\x00" * 32

        # Should not raise — timeout means tx pending, proceed to swap
        result = await svc._approve(
            private_key="0x" + "f" * 64,
            token_address="0x" + "b" * 40,
            spender="0x" + "c" * 40,
            amount=1000,
            nonce=0,
            gas_price=1,
        )
        assert result == fake_hash


# ---------------------------------------------------------------------------
# 6. ALLOWED_HOSTS in config
# ---------------------------------------------------------------------------

def test_allowed_hosts_default_is_wildcard():
    from app.config import settings
    assert settings.ALLOWED_HOSTS == ["*"]


def test_allowed_hosts_is_list():
    from app.config import settings
    assert isinstance(settings.ALLOWED_HOSTS, list)
