"""Unit tests for Telegram bot command handler (_handle_command)."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.telegram_callback_service import _handle_command


def _make_settings(
    bot_enabled=True,
    auto_trade=True,
    auto_tuning_enabled=False,
    tuning_frequency="weekly",
    risk_percent=1.0,
    max_open_trades=5,
    daily_loss_limit_percent=3.0,
    max_drawdown_percent=10.0,
    consecutive_loss_limit=3,
    paper_balance=10000.0,
    symbol="BTCUSDT",
    leverage=10,
    scan_all_coins=False,
    max_scan_coins=50,
    min_volume_filter=5_000_000.0,
    scanner_watchlist=None,
    user_id=1,
):
    s = MagicMock()
    s.bot_enabled = bot_enabled
    s.auto_trade = auto_trade
    s.auto_tuning_enabled = auto_tuning_enabled
    s.tuning_frequency = tuning_frequency
    s.risk_percent = risk_percent
    s.max_open_trades = max_open_trades
    s.daily_loss_limit_percent = daily_loss_limit_percent
    s.max_drawdown_percent = max_drawdown_percent
    s.consecutive_loss_limit = consecutive_loss_limit
    s.paper_balance = paper_balance
    s.symbol = symbol
    s.leverage = leverage
    s.scan_all_coins = scan_all_coins
    s.max_scan_coins = max_scan_coins
    s.min_volume_filter = min_volume_filter
    s.scanner_watchlist = scanner_watchlist or ["BTCUSDT", "ETHUSDT"]
    s.user_id = user_id
    return s


def _make_db(settings_list=None, scalar_returns=None):
    """Build async DB mock. scalar_returns: list of values returned by .scalar() in sequence."""
    db = AsyncMock()
    settings_list = settings_list if settings_list is not None else [_make_settings()]

    # scalars().all() returns settings list
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = settings_list
    scalars_mock.scalars.return_value = scalars_mock

    # For scalar() calls (counts / sums) — cycle through provided values
    scalar_values = scalar_returns or []
    scalar_iter = iter(scalar_values)

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    def _scalar():
        try:
            return next(scalar_iter)
        except StopIteration:
            return 0

    execute_result.scalar = _scalar

    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

class TestHelp:
    @pytest.mark.asyncio
    async def test_help_lists_commands(self):
        db = _make_db()
        reply = await _handle_command("/help", db)
        assert "/status" in reply
        assert "/risk" in reply
        assert "/pause" in reply
        assert "/resume" in reply
        assert "/enable_autotrade" in reply
        assert "/close_all" in reply
        assert "/report" in reply

    @pytest.mark.asyncio
    async def test_help_no_db_needed(self):
        db = AsyncMock()  # should not be called
        reply = await _handle_command("/help", db)
        db.execute.assert_not_called()
        assert "Commands" in reply


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

class TestStatus:
    @pytest.mark.asyncio
    async def test_status_running_bot(self):
        s = _make_settings(bot_enabled=True, auto_trade=True, symbol="ETHUSDT", leverage=5)
        db = _make_db([s])
        reply = await _handle_command("/status", db)
        assert "Running" in reply
        assert "ETHUSDT" in reply
        assert "5x" in reply

    @pytest.mark.asyncio
    async def test_status_paused_bot(self):
        s = _make_settings(bot_enabled=False)
        db = _make_db([s])
        reply = await _handle_command("/status", db)
        assert "Paused" in reply

    @pytest.mark.asyncio
    async def test_status_scan_all_coins(self):
        s = _make_settings(scan_all_coins=True, max_scan_coins=30, min_volume_filter=10_000_000.0)
        db = _make_db([s])
        reply = await _handle_command("/status", db)
        assert "All coins" in reply
        assert "30" in reply

    @pytest.mark.asyncio
    async def test_status_watchlist_mode(self):
        s = _make_settings(scan_all_coins=False, scanner_watchlist=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        db = _make_db([s])
        reply = await _handle_command("/status", db)
        assert "Watchlist" in reply
        assert "3" in reply

    @pytest.mark.asyncio
    async def test_status_no_settings(self):
        db = _make_db([])
        reply = await _handle_command("/status", db)
        assert "No bot settings" in reply or "No settings" in reply


# ---------------------------------------------------------------------------
# /risk
# ---------------------------------------------------------------------------

class TestRisk:
    @pytest.mark.asyncio
    async def test_risk_calls_risk_service(self):
        s = _make_settings(risk_percent=1.5)
        db = _make_db([s])
        fake_risk = {
            "status": "SAFE",
            "daily_loss_percent": 0.5,
            "daily_loss_limit_percent": 3.0,
            "current_drawdown_percent": 1.0,
            "max_drawdown_percent": 10.0,
            "consecutive_losses": 1,
            "consecutive_loss_limit": 3,
            "open_positions": 2,
            "max_open_trades": 5,
        }
        with patch("app.services.telegram_callback_service.RiskService") as MockRisk:
            MockRisk.return_value.get_risk_status = AsyncMock(return_value=fake_risk)
            reply = await _handle_command("/risk", db)
        assert "SAFE" in reply
        assert "0.50%" in reply
        assert "1.5" in reply  # risk_percent

    @pytest.mark.asyncio
    async def test_risk_critical_shows_red(self):
        s = _make_settings()
        db = _make_db([s])
        fake_risk = {
            "status": "CRITICAL",
            "daily_loss_percent": 3.2,
            "daily_loss_limit_percent": 3.0,
            "current_drawdown_percent": 5.0,
            "max_drawdown_percent": 10.0,
            "consecutive_losses": 4,
            "consecutive_loss_limit": 3,
            "open_positions": 0,
            "max_open_trades": 5,
        }
        with patch("app.services.telegram_callback_service.RiskService") as MockRisk:
            MockRisk.return_value.get_risk_status = AsyncMock(return_value=fake_risk)
            reply = await _handle_command("/risk", db)
        assert "CRITICAL" in reply
        assert "🔴" in reply


# ---------------------------------------------------------------------------
# /pause and /resume
# ---------------------------------------------------------------------------

class TestPauseResume:
    @pytest.mark.asyncio
    async def test_pause_disables_bot(self):
        s = _make_settings(bot_enabled=True)
        db = _make_db([s])
        reply = await _handle_command("/pause", db)
        assert s.bot_enabled is False
        db.commit.assert_awaited_once()
        assert "paused" in reply.lower()

    @pytest.mark.asyncio
    async def test_resume_enables_bot(self):
        s = _make_settings(bot_enabled=False)
        db = _make_db([s])
        reply = await _handle_command("/resume", db)
        assert s.bot_enabled is True
        db.commit.assert_awaited_once()
        assert "resumed" in reply.lower()

    @pytest.mark.asyncio
    async def test_pause_multiple_users(self):
        s1 = _make_settings(bot_enabled=True, user_id=1)
        s2 = _make_settings(bot_enabled=True, user_id=2)
        db = _make_db([s1, s2])
        await _handle_command("/pause", db)
        assert s1.bot_enabled is False
        assert s2.bot_enabled is False


# ---------------------------------------------------------------------------
# /enable_autotrade
# ---------------------------------------------------------------------------

class TestEnableAutotrade:
    @pytest.mark.asyncio
    async def test_toggle_on_to_off(self):
        s = _make_settings(auto_trade=True)
        db = _make_db([s])
        reply = await _handle_command("/enable_autotrade", db)
        assert s.auto_trade is False
        assert "OFF" in reply
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_toggle_off_to_on(self):
        s = _make_settings(auto_trade=False)
        db = _make_db([s])
        reply = await _handle_command("/enable_autotrade", db)
        assert s.auto_trade is True
        assert "ON" in reply


# ---------------------------------------------------------------------------
# /report
# ---------------------------------------------------------------------------

class TestReport:
    @pytest.mark.asyncio
    async def test_report_shows_stats(self):
        s = _make_settings(paper_balance=12500.0)
        # scalar() calls: total=10, wins=7, total_pnl=300.0, open=2
        db = _make_db([s], scalar_returns=[10, 7, 300.0, 2])
        reply = await _handle_command("/report", db)
        assert "10" in reply   # total trades
        assert "7W" in reply   # wins
        assert "70.0%" in reply  # win rate
        assert "300" in reply  # pnl
        assert "12,500" in reply  # balance

    @pytest.mark.asyncio
    async def test_report_zero_trades(self):
        s = _make_settings()
        db = _make_db([s], scalar_returns=[0, 0, 0.0, 0])
        reply = await _handle_command("/report", db)
        assert "0" in reply
        assert "0.0%" in reply


# ---------------------------------------------------------------------------
# /close_all
# ---------------------------------------------------------------------------

class TestCloseAll:
    @pytest.mark.asyncio
    async def test_close_all_open_trades(self):
        from app.models.trade import Trade, TradeStatus

        s = _make_settings()
        db = AsyncMock()

        # First execute → settings query
        settings_result = MagicMock()
        settings_result.scalars.return_value.all.return_value = [s]

        # Build fake open trades
        t1 = MagicMock(spec=Trade)
        t1.entry_price = 50000.0
        t2 = MagicMock(spec=Trade)
        t2.entry_price = 3000.0

        # Second execute → open trades query
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = [t1, t2]

        db.execute = AsyncMock(side_effect=[settings_result, trades_result])
        db.commit = AsyncMock()

        reply = await _handle_command("/close_all", db)

        assert t1.status == TradeStatus.CLOSED
        assert t1.exit_price == 50000.0
        assert t1.pnl == 0.0
        assert t2.status == TradeStatus.CLOSED
        db.commit.assert_awaited_once()
        assert "2" in reply

    @pytest.mark.asyncio
    async def test_close_all_no_open_trades(self):
        s = _make_settings()
        db = AsyncMock()

        settings_result = MagicMock()
        settings_result.scalars.return_value.all.return_value = [s]
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(side_effect=[settings_result, trades_result])
        db.commit = AsyncMock()

        reply = await _handle_command("/close_all", db)
        assert "No open" in reply


# ---------------------------------------------------------------------------
# Unknown command
# ---------------------------------------------------------------------------

class TestUnknown:
    @pytest.mark.asyncio
    async def test_unknown_command(self):
        s = _make_settings()
        db = _make_db([s])
        reply = await _handle_command("/foobar", db)
        assert "Unknown" in reply
        assert "/foobar" in reply
