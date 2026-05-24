"""Unit tests for TuningService._compute_metrics and _recommend."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

from app.services.tuning_service import TuningService, MIN_RISK, MAX_RISK


def _make_settings(risk_percent=1.0, consecutive_loss_limit=3):
    s = MagicMock()
    s.risk_percent = risk_percent
    s.consecutive_loss_limit = consecutive_loss_limit
    s.auto_tuning_enabled = True
    s.tuning_frequency = "weekly"
    s.require_manual_approval_for_tuning = True
    return s


def _make_trade(pnl):
    t = MagicMock()
    t.pnl = pnl
    return t


def _make_svc():
    db = AsyncMock()
    return TuningService(db)


class TestComputeMetrics:
    def test_empty(self):
        svc = _make_svc()
        m = svc._compute_metrics([])
        assert m["total_trades"] == 0

    def test_all_wins(self):
        svc = _make_svc()
        trades = [_make_trade(10), _make_trade(5), _make_trade(7)]
        m = svc._compute_metrics(trades)
        assert m["win_rate"] == 1.0
        assert m["profit_factor"] == 99.0  # no losses → capped at 99

    def test_all_losses(self):
        svc = _make_svc()
        trades = [_make_trade(-10), _make_trade(-5)]
        m = svc._compute_metrics(trades)
        assert m["win_rate"] == 0.0
        assert m["profit_factor"] == 0.0

    def test_mixed(self):
        svc = _make_svc()
        trades = [_make_trade(10), _make_trade(-5), _make_trade(8), _make_trade(-3)]
        m = svc._compute_metrics(trades)
        assert m["win_rate"] == 0.5
        assert m["profit_factor"] == pytest.approx(18 / 8, rel=0.01)

    def test_consecutive_losses(self):
        svc = _make_svc()
        trades = [_make_trade(5), _make_trade(-1), _make_trade(-2), _make_trade(-3), _make_trade(1)]
        m = svc._compute_metrics(trades)
        assert m["max_consecutive_losses"] == 3

    def test_none_pnl_skipped(self):
        svc = _make_svc()
        trades = [_make_trade(None), _make_trade(10), _make_trade(-5)]
        m = svc._compute_metrics(trades)
        assert m["total_trades"] == 2


class TestRecommend:
    def test_insufficient_trades(self):
        svc = _make_svc()
        s = _make_settings(risk_percent=1.0)
        metrics = {"total_trades": 3, "win_rate": 0.2, "profit_factor": 0.5, "max_consecutive_losses": 0}
        new_risk, reason = svc._recommend(metrics, s)
        assert new_risk == 1.0
        assert reason == ""

    def test_low_win_rate_decreases(self):
        svc = _make_svc()
        s = _make_settings(risk_percent=1.0)
        metrics = {"total_trades": 10, "win_rate": 0.30, "profit_factor": 0.5, "max_consecutive_losses": 0}
        new_risk, reason = svc._recommend(metrics, s)
        assert new_risk < 1.0
        assert "Win rate" in reason

    def test_consecutive_losses_decreases(self):
        svc = _make_svc()
        s = _make_settings(risk_percent=1.5, consecutive_loss_limit=3)
        metrics = {"total_trades": 10, "win_rate": 0.45, "profit_factor": 1.0, "max_consecutive_losses": 3}
        new_risk, reason = svc._recommend(metrics, s)
        assert new_risk < 1.5
        assert "consecutive" in reason

    def test_strong_performance_increases(self):
        svc = _make_svc()
        s = _make_settings(risk_percent=1.0)
        metrics = {"total_trades": 15, "win_rate": 0.65, "profit_factor": 2.0, "max_consecutive_losses": 1}
        new_risk, reason = svc._recommend(metrics, s)
        assert new_risk > 1.0
        assert "increase" in reason.lower()

    def test_min_risk_floor(self):
        svc = _make_svc()
        s = _make_settings(risk_percent=0.1)
        metrics = {"total_trades": 10, "win_rate": 0.20, "profit_factor": 0.3, "max_consecutive_losses": 0}
        new_risk, reason = svc._recommend(metrics, s)
        assert new_risk >= MIN_RISK

    def test_max_risk_ceiling(self):
        svc = _make_svc()
        s = _make_settings(risk_percent=5.0)
        metrics = {"total_trades": 15, "win_rate": 0.70, "profit_factor": 3.0, "max_consecutive_losses": 0}
        new_risk, reason = svc._recommend(metrics, s)
        assert new_risk <= MAX_RISK

    def test_neutral_no_change(self):
        svc = _make_svc()
        s = _make_settings(risk_percent=1.0)
        metrics = {"total_trades": 10, "win_rate": 0.50, "profit_factor": 1.2, "max_consecutive_losses": 1}
        new_risk, reason = svc._recommend(metrics, s)
        assert new_risk == 1.0
        assert reason == ""
