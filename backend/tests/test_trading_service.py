import pytest
import pytest_asyncio
from datetime import datetime, timezone

from app.services.trading_service import TradingService
from app.models.trade import Trade, TradeDirection, TradeStatus
from app.models.settings import Settings
from app.models.user import User
from app.schemas.trade import TradeCreate, TradeClose
from app.core.exceptions import MaxTradesExceededError, RiskLimitExceededError
from app.core.security import hash_password


@pytest_asyncio.fixture
async def trading_user(db):
    user = User(
        email="trader@unittest.com",
        username="trader_unit",
        hashed_password=hash_password("Pass1234"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    settings = Settings(
        user_id=user.id,
        risk_percent=2.0,
        max_open_trades=3,
        daily_loss_limit_percent=3.0,
        max_drawdown_percent=10.0,
        consecutive_loss_limit=3,
    )
    db.add(settings)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def svc(db):
    return TradingService(db)


def _long_trade_data(risk_percent: float = 1.0) -> TradeCreate:
    return TradeCreate(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit=52000.0,
        risk_percent=risk_percent,
        leverage=10,
    )


def _short_trade_data(risk_percent: float = 1.0) -> TradeCreate:
    return TradeCreate(
        symbol="BTCUSDT",
        direction=TradeDirection.SHORT,
        entry_price=50000.0,
        stop_loss=51000.0,
        take_profit=48000.0,
        risk_percent=risk_percent,
        leverage=10,
    )


async def _fill_open_trades(db, user_id: int, count: int) -> None:
    for _ in range(count):
        db.add(Trade(
            user_id=user_id,
            symbol="ETHUSDT",
            direction=TradeDirection.LONG,
            status=TradeStatus.OPEN,
            entry_price=3000.0,
            stop_loss=2900.0,
            take_profit=3200.0,
            quantity=0.1,
            leverage=10,
            risk_amount=100.0,
            risk_percent=1.0,
            opened_at=datetime.now(timezone.utc),
        ))
    await db.flush()


# ── open_trade ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_open_trade_sufficient_balance(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _long_trade_data(), balance=10000.0)

    assert trade.id is not None
    assert trade.status == TradeStatus.OPEN
    assert trade.direction == TradeDirection.LONG
    assert trade.symbol == "BTCUSDT"
    # qty = (10000 * 0.01) / abs(50000 - 49000) = 100 / 1000 = 0.1
    assert trade.quantity == pytest.approx(0.1, rel=1e-4)
    assert trade.risk_amount == pytest.approx(100.0, rel=1e-4)
    assert trade.entry_price == 50000.0
    assert trade.stop_loss == 49000.0
    assert trade.take_profit == 52000.0


@pytest.mark.asyncio
async def test_open_trade_max_trades_exceeded(svc, trading_user, db):
    # max_open_trades = 3; insert 3 open trades first
    await _fill_open_trades(db, trading_user.id, count=3)

    with pytest.raises(MaxTradesExceededError):
        await svc.create_trade(trading_user.id, _long_trade_data(), balance=10000.0)


@pytest.mark.asyncio
async def test_open_trade_risk_limit_exceeded(svc, trading_user):
    # settings.risk_percent = 2.0 → max allowed = 4.0; use 5.0 to exceed
    with pytest.raises(RiskLimitExceededError):
        await svc.create_trade(trading_user.id, _long_trade_data(risk_percent=5.0), balance=10000.0)


# ── close_trade PnL ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close_long_profit(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _long_trade_data(), balance=10000.0)
    closed = await svc.close_trade(trade.id, trading_user.id, TradeClose(exit_price=51000.0))

    # pnl = (51000 - 50000) * 0.1 * 10 = 1000
    assert closed.pnl == pytest.approx(1000.0, rel=1e-4)
    assert closed.pnl > 0
    assert closed.status == TradeStatus.CLOSED
    assert closed.exit_price == 51000.0


@pytest.mark.asyncio
async def test_close_long_loss(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _long_trade_data(), balance=10000.0)
    closed = await svc.close_trade(trade.id, trading_user.id, TradeClose(exit_price=49500.0))

    # pnl = (49500 - 50000) * 0.1 * 10 = -500
    assert closed.pnl == pytest.approx(-500.0, rel=1e-4)
    assert closed.pnl < 0


@pytest.mark.asyncio
async def test_close_short_profit(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _short_trade_data(), balance=10000.0)
    closed = await svc.close_trade(trade.id, trading_user.id, TradeClose(exit_price=48000.0))

    # pnl = (50000 - 48000) * qty * 10 > 0
    assert closed.pnl > 0
    assert closed.status == TradeStatus.CLOSED


@pytest.mark.asyncio
async def test_close_short_loss(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _short_trade_data(), balance=10000.0)
    closed = await svc.close_trade(trade.id, trading_user.id, TradeClose(exit_price=51000.0))

    # pnl = (50000 - 51000) * qty * 10 < 0
    assert closed.pnl < 0


# ── SL / TP hit ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close_long_sl_hit(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _long_trade_data(), balance=10000.0)
    closed = await svc.close_trade(
        trade.id, trading_user.id,
        TradeClose(exit_price=trade.stop_loss, notes="SL hit"),
    )

    # pnl = (49000 - 50000) * 0.1 * 10 = -1000
    assert closed.pnl == pytest.approx(-1000.0, rel=1e-4)
    assert closed.pnl < 0
    assert closed.notes == "SL hit"
    assert closed.status == TradeStatus.CLOSED


@pytest.mark.asyncio
async def test_close_long_tp_hit(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _long_trade_data(), balance=10000.0)
    closed = await svc.close_trade(
        trade.id, trading_user.id,
        TradeClose(exit_price=trade.take_profit, notes="TP hit"),
    )

    # pnl = (52000 - 50000) * 0.1 * 10 = 2000
    assert closed.pnl == pytest.approx(2000.0, rel=1e-4)
    assert closed.pnl > 0
    assert closed.notes == "TP hit"
    assert closed.status == TradeStatus.CLOSED


@pytest.mark.asyncio
async def test_close_short_sl_hit(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _short_trade_data(), balance=10000.0)
    # SHORT SL is above entry (51000)
    closed = await svc.close_trade(
        trade.id, trading_user.id,
        TradeClose(exit_price=trade.stop_loss, notes="SL hit"),
    )
    assert closed.pnl < 0


@pytest.mark.asyncio
async def test_close_short_tp_hit(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _short_trade_data(), balance=10000.0)
    # SHORT TP is below entry (48000)
    closed = await svc.close_trade(
        trade.id, trading_user.id,
        TradeClose(exit_price=trade.take_profit, notes="TP hit"),
    )
    assert closed.pnl > 0


@pytest.mark.asyncio
async def test_close_nonexistent_trade_raises(svc, trading_user):
    with pytest.raises(ValueError, match="Trade not found"):
        await svc.close_trade(99999, trading_user.id, TradeClose(exit_price=50000.0))


@pytest.mark.asyncio
async def test_close_already_closed_trade_raises(svc, trading_user):
    trade = await svc.create_trade(trading_user.id, _long_trade_data(), balance=10000.0)
    await svc.close_trade(trade.id, trading_user.id, TradeClose(exit_price=51000.0))

    with pytest.raises(ValueError, match="not open"):
        await svc.close_trade(trade.id, trading_user.id, TradeClose(exit_price=51000.0))
