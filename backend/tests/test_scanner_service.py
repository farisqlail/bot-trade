import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.scanner_service import ScannerService
from app.models.settings import Settings
from app.models.user import User
from app.core.security import hash_password


# ── helpers ──────────────────────────────────────────────────────────────────

def _market_data(
    close_0: float = 100.0,
    close_last: float = 100.0,
    change_24h: float = 0.0,
    polymarket_bias_score: float = 0.0,
    price: float = 100.0,
) -> dict:
    """Build minimal market_data dict for _heuristic_signal."""
    return {
        "price": price,
        "change_24h": change_24h,
        "volume_24h": 5_000_000.0,
        "polymarket_bias_score": polymarket_bias_score,
        "polymarket_market_count": 2,
        "polymarket_markets": [],
        "candles": [
            {"open": close_0, "high": close_0, "low": close_0, "close": close_0, "volume": 100},
            {"open": close_last, "high": close_last, "low": close_last, "close": close_last, "volume": 100},
        ],
    }


# ── _heuristic_signal unit tests (sync, no mocks needed) ─────────────────────

def test_heuristic_buy_signal():
    scanner = ScannerService.__new__(ScannerService)
    data = _market_data(close_0=100.0, close_last=102.0, change_24h=3.0, polymarket_bias_score=0.2, price=102.0)

    result = scanner._heuristic_signal("BTCUSDT", data)

    # score = (0.02*0.45) + (0.03*0.25) + (0.2*0.30) = 0.009 + 0.0075 + 0.06 = 0.0765 → BUY
    assert result["recommended_action"] == "BUY"
    assert result["trend"] == "BULLISH"
    assert result["score"] > 0
    assert result["symbol"] == "BTCUSDT"


def test_heuristic_strong_buy_signal():
    scanner = ScannerService.__new__(ScannerService)
    # High positive values → score well above 0.005
    data = _market_data(close_0=100.0, close_last=105.0, change_24h=8.0, polymarket_bias_score=0.5, price=105.0)

    result = scanner._heuristic_signal("ETHUSDT", data)

    assert result["recommended_action"] == "BUY"
    assert result["sentiment"] == "STRONG_BUY"
    assert result["score"] >= 0.005


def test_heuristic_sell_signal():
    scanner = ScannerService.__new__(ScannerService)
    data = _market_data(close_0=100.0, close_last=98.0, change_24h=-3.0, polymarket_bias_score=-0.2, price=98.0)

    result = scanner._heuristic_signal("SOLUSDT", data)

    # score = (-0.02*0.45) + (-0.03*0.25) + (-0.2*0.30) = negative → SELL
    assert result["recommended_action"] == "SELL"
    assert result["trend"] == "BEARISH"
    assert result["score"] < 0


def test_heuristic_strong_sell_signal():
    scanner = ScannerService.__new__(ScannerService)
    data = _market_data(close_0=100.0, close_last=94.0, change_24h=-8.0, polymarket_bias_score=-0.5, price=94.0)

    result = scanner._heuristic_signal("XRPUSDT", data)

    assert result["recommended_action"] == "SELL"
    assert result["sentiment"] == "STRONG_SELL"
    assert result["score"] <= -0.005


def test_heuristic_hold_signal():
    scanner = ScannerService.__new__(ScannerService)
    # Zero momentum, zero change, zero polymarket → score = 0 → HOLD
    data = _market_data(close_0=100.0, close_last=100.0, change_24h=0.0, polymarket_bias_score=0.0, price=100.0)

    result = scanner._heuristic_signal("DOGEUSDT", data)

    assert result["recommended_action"] == "HOLD"
    assert result["trend"] == "SIDEWAYS"
    assert result["sentiment"] == "HOLD"
    assert abs(result["score"]) < 0.001


def test_heuristic_sl_tp_direction_buy():
    scanner = ScannerService.__new__(ScannerService)
    data = _market_data(close_0=100.0, close_last=102.0, change_24h=2.0, polymarket_bias_score=0.1, price=102.0)

    result = scanner._heuristic_signal("BTCUSDT", data)

    # BUY: SL below price, TP above price
    assert result["suggested_sl"] < result["price_at_analysis"]
    assert result["suggested_tp"] > result["price_at_analysis"]


def test_heuristic_sl_tp_direction_sell():
    scanner = ScannerService.__new__(ScannerService)
    data = _market_data(close_0=100.0, close_last=98.0, change_24h=-2.0, polymarket_bias_score=-0.1, price=98.0)

    result = scanner._heuristic_signal("BTCUSDT", data)

    # SELL: SL above price, TP below price
    assert result["suggested_sl"] > result["price_at_analysis"]
    assert result["suggested_tp"] < result["price_at_analysis"]


def test_heuristic_empty_candles_graceful():
    scanner = ScannerService.__new__(ScannerService)
    data = {
        "price": 100.0,
        "change_24h": 1.0,
        "volume_24h": 1_000_000.0,
        "polymarket_bias_score": 0.0,
        "polymarket_market_count": 0,
        "polymarket_markets": [],
        "candles": [],  # no candles → momentum = 0
    }

    result = scanner._heuristic_signal("BNBUSDT", data)

    # momentum=0, change_score=0.01, sentiment_score=0 → score=0.0025 → BUY
    assert result["recommended_action"] in {"BUY", "HOLD"}
    assert isinstance(result["score"], float)


# ── scan_opportunities: all-coins volume filter ───────────────────────────────

@pytest_asyncio.fixture
async def scanner_user(db):
    user = User(
        email="scanner@unittest.com",
        username="scanner_unit",
        hashed_password=hash_password("Pass1234"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    settings = Settings(user_id=user.id)
    settings.scan_all_coins = True
    settings.min_volume_filter = 1_000_000.0
    settings.max_scan_coins = 50
    settings.ai_analysis_enabled = False   # skip DeepSeek calls
    db.add(settings)
    await db.flush()
    return user


def _mock_market_data(symbol: str = "BTCUSDT") -> dict:
    return {
        "price": 50000.0,
        "change_24h": 1.5,
        "volume_24h": 5_000_000.0,
        "polymarket_bias_score": 0.1,
        "polymarket_market_count": 1,
        "polymarket_markets": [],
        "candles": [
            {"open": 49000, "high": 50500, "low": 48500, "close": 49000, "volume": 1000},
            {"open": 50000, "high": 51000, "low": 49500, "close": 50000, "volume": 1200},
        ],
    }


@pytest.mark.asyncio
async def test_scan_all_coins_calls_get_all_tickers_with_min_volume(scanner_user, db):
    """scan_opportunities passes min_volume_filter to get_all_tickers."""
    scanner = ScannerService(db)

    eligible_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    scanner.exchange_svc.get_all_tickers = AsyncMock(return_value=[
        {"symbol": s, "turnover_24h": 5_000_000.0, "price": 50000.0,
         "change_24h": 1.0, "volume": 1000.0}
        for s in eligible_symbols
    ])
    scanner.exchange_svc.get_market_data = AsyncMock(side_effect=lambda s: _mock_market_data(s))
    scanner.ai_svc.save_heuristic_result = AsyncMock()
    scanner.ai_svc.analyze_market = AsyncMock()

    await scanner.scan_opportunities(scanner_user.id, deep_analysis=False, execute_paper=False)

    scanner.exchange_svc.get_all_tickers.assert_called_once_with(min_turnover_usd=1_000_000.0)


@pytest.mark.asyncio
async def test_scan_all_coins_only_fetches_returned_symbols(scanner_user, db):
    """get_market_data called only for symbols returned by get_all_tickers."""
    scanner = ScannerService(db)

    eligible_symbols = ["BTCUSDT", "ETHUSDT"]
    scanner.exchange_svc.get_all_tickers = AsyncMock(return_value=[
        {"symbol": s, "turnover_24h": 5_000_000.0, "price": 100.0,
         "change_24h": 0.5, "volume": 500.0}
        for s in eligible_symbols
    ])
    scanner.exchange_svc.get_market_data = AsyncMock(side_effect=lambda s: _mock_market_data(s))
    scanner.ai_svc.save_heuristic_result = AsyncMock()
    scanner.ai_svc.analyze_market = AsyncMock()

    results = await scanner.scan_opportunities(scanner_user.id, deep_analysis=False, execute_paper=False)

    result_symbols = {r["symbol"] for r in results}
    assert result_symbols == set(eligible_symbols)
    assert scanner.exchange_svc.get_market_data.call_count == len(eligible_symbols)


@pytest.mark.asyncio
async def test_scan_all_coins_respects_max_scan_coins(scanner_user, db):
    """Watchlist truncated to max_scan_coins even if more tickers returned."""
    # Update settings to max_scan_coins=2
    from sqlalchemy import select
    from app.models.settings import Settings as SettingsModel
    result = await db.execute(select(SettingsModel).where(SettingsModel.user_id == scanner_user.id))
    settings = result.scalar_one()
    settings.max_scan_coins = 2
    await db.flush()

    scanner = ScannerService(db)

    all_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    scanner.exchange_svc.get_all_tickers = AsyncMock(return_value=[
        {"symbol": s, "turnover_24h": 5_000_000.0, "price": 100.0, "change_24h": 0.5, "volume": 500.0}
        for s in all_symbols
    ])
    scanner.exchange_svc.get_market_data = AsyncMock(side_effect=lambda s: _mock_market_data(s))
    scanner.ai_svc.save_heuristic_result = AsyncMock()
    scanner.ai_svc.analyze_market = AsyncMock()

    results = await scanner.scan_opportunities(scanner_user.id, deep_analysis=False, execute_paper=False)

    # Only 2 coins fetched/returned (max_scan_coins=2)
    assert len(results) == 2
    assert scanner.exchange_svc.get_market_data.call_count == 2


@pytest.mark.asyncio
async def test_scan_all_coins_results_sorted_by_score(scanner_user, db):
    """Results sorted by abs(score) descending."""
    scanner = ScannerService(db)

    scanner.exchange_svc.get_all_tickers = AsyncMock(return_value=[
        {"symbol": "BTCUSDT", "turnover_24h": 5_000_000.0, "price": 100.0, "change_24h": 0.0, "volume": 100.0},
        {"symbol": "ETHUSDT", "turnover_24h": 8_000_000.0, "price": 100.0, "change_24h": 0.0, "volume": 100.0},
    ])

    def _varied_market_data(symbol: str) -> dict:
        # BTCUSDT: strong signal, ETHUSDT: weak signal
        if symbol == "BTCUSDT":
            return _market_data(close_0=100.0, close_last=105.0, change_24h=5.0, polymarket_bias_score=0.4, price=105.0)
        return _market_data(close_0=100.0, close_last=100.1, change_24h=0.1, polymarket_bias_score=0.01, price=100.1)

    scanner.exchange_svc.get_market_data = AsyncMock(side_effect=_varied_market_data)
    scanner.ai_svc.save_heuristic_result = AsyncMock()
    scanner.ai_svc.analyze_market = AsyncMock()

    results = await scanner.scan_opportunities(scanner_user.id, deep_analysis=False, execute_paper=False)

    assert len(results) == 2
    assert abs(results[0]["score"]) >= abs(results[1]["score"])
