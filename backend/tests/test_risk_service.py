import pytest
import pytest_asyncio
from datetime import datetime, timezone

from app.services.risk_service import RiskService
from app.models.trade import Trade, TradeDirection, TradeStatus
from app.models.risk_event import RiskEvent, RiskEventType
from app.models.settings import Settings
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy import select


@pytest_asyncio.fixture
async def risk_user(db):
    user = User(
        email="risk@unittest.com",
        username="risk_unit",
        hashed_password=hash_password("Pass1234"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    settings = Settings(
        user_id=user.id,
        risk_percent=2.0,
        max_open_trades=5,
        daily_loss_limit_percent=5.0,   # 5% daily loss limit
        max_drawdown_percent=15.0,
        consecutive_loss_limit=3,
    )
    db.add(settings)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def svc(db):
    return RiskService(db)


async def _insert_closed_trade(db, user_id: int, pnl: float, symbol: str = "BTCUSDT") -> Trade:
    trade = Trade(
        user_id=user_id,
        symbol=symbol,
        direction=TradeDirection.LONG,
        status=TradeStatus.CLOSED,
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit=52000.0,
        quantity=0.1,
        leverage=10,
        risk_amount=100.0,
        risk_percent=1.0,
        pnl=pnl,
        opened_at=datetime.now(timezone.utc),
        closed_at=datetime.now(timezone.utc),
    )
    db.add(trade)
    await db.flush()
    return trade


# ── daily loss limit ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_daily_loss_limit_critical(svc, risk_user, db):
    # balance=10000, limit=5% → threshold=500; insert loss of 600 → 6% → CRITICAL
    await _insert_closed_trade(db, risk_user.id, pnl=-600.0)

    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert status["status"] == "CRITICAL"
    assert status["daily_loss_percent"] == pytest.approx(6.0, rel=1e-2)
    assert status["daily_loss_limit_percent"] == 5.0


@pytest.mark.asyncio
async def test_daily_loss_limit_danger(svc, risk_user, db):
    # 5% * 0.8 = 4% threshold; insert loss of 420 → 4.2% → DANGER
    await _insert_closed_trade(db, risk_user.id, pnl=-420.0)

    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert status["status"] == "DANGER"


@pytest.mark.asyncio
async def test_daily_loss_limit_warning(svc, risk_user, db):
    # 5% * 0.5 = 2.5% threshold; insert loss of 300 → 3% → WARNING
    await _insert_closed_trade(db, risk_user.id, pnl=-300.0)

    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert status["status"] == "WARNING"


@pytest.mark.asyncio
async def test_daily_loss_limit_safe(svc, risk_user, db):
    # Profit trade → no loss → SAFE
    await _insert_closed_trade(db, risk_user.id, pnl=200.0)

    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert status["status"] == "SAFE"
    assert status["daily_loss_percent"] == pytest.approx(0.0, abs=1e-4)


@pytest.mark.asyncio
async def test_check_and_log_daily_loss_creates_risk_event(svc, risk_user, db):
    # Trigger CRITICAL → check_and_log should write RiskEvent
    await _insert_closed_trade(db, risk_user.id, pnl=-600.0)

    await svc.check_and_log_risk_events(risk_user.id, balance=10000.0)

    result = await db.execute(
        select(RiskEvent).where(
            RiskEvent.user_id == risk_user.id,
            RiskEvent.event_type == RiskEventType.DAILY_LOSS_LIMIT,
        )
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].triggered_value == pytest.approx(6.0, rel=1e-1)


# ── consecutive loss limit ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consecutive_loss_limit_counted(svc, risk_user, db):
    # 3 losing trades in a row
    for _ in range(3):
        await _insert_closed_trade(db, risk_user.id, pnl=-100.0)

    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert status["consecutive_losses"] == 3
    assert status["consecutive_loss_limit"] == 3


@pytest.mark.asyncio
async def test_consecutive_loss_resets_on_win(svc, risk_user, db):
    # 2 losses, then 1 win → consecutive_losses = 0
    await _insert_closed_trade(db, risk_user.id, pnl=-100.0)
    await _insert_closed_trade(db, risk_user.id, pnl=-100.0)
    await _insert_closed_trade(db, risk_user.id, pnl=200.0)

    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert status["consecutive_losses"] == 0


@pytest.mark.asyncio
async def test_consecutive_loss_limit_creates_risk_event(svc, risk_user, db):
    # Hit consecutive_loss_limit (3)
    for _ in range(3):
        await _insert_closed_trade(db, risk_user.id, pnl=-100.0)

    await svc.check_and_log_risk_events(risk_user.id, balance=10000.0)

    result = await db.execute(
        select(RiskEvent).where(
            RiskEvent.user_id == risk_user.id,
            RiskEvent.event_type == RiskEventType.CONSECUTIVE_LOSSES,
        )
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].triggered_value == 3


@pytest.mark.asyncio
async def test_consecutive_loss_below_limit_no_event(svc, risk_user, db):
    # 2 losses < limit of 3 → no event
    for _ in range(2):
        await _insert_closed_trade(db, risk_user.id, pnl=-100.0)

    await svc.check_and_log_risk_events(risk_user.id, balance=10000.0)

    result = await db.execute(
        select(RiskEvent).where(
            RiskEvent.user_id == risk_user.id,
            RiskEvent.event_type == RiskEventType.CONSECUTIVE_LOSSES,
        )
    )
    assert result.scalars().first() is None


# ── drawdown limit ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_drawdown_limit_present_in_status(svc, risk_user):
    # Drawdown calculation is currently placeholder (always 0.0).
    # Verify the limit is surfaced correctly from settings.
    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert "max_drawdown_percent" in status
    assert status["max_drawdown_percent"] == 15.0
    assert "current_drawdown_percent" in status


@pytest.mark.asyncio
async def test_drawdown_safe_with_no_trades(svc, risk_user):
    status = await svc.get_risk_status(risk_user.id, balance=10000.0)

    assert status["status"] == "SAFE"
    assert status["current_drawdown_percent"] == 0.0


# ── no settings fallback ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_status_no_settings_returns_defaults(db):
    svc = RiskService(db)
    # user_id 99999 has no settings
    status = await svc.get_risk_status(99999, balance=10000.0)

    assert status["status"] == "SAFE"
    assert status["daily_loss_limit_percent"] == 3.0
    assert status["consecutive_loss_limit"] == 3
