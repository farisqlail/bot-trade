import pytest
from unittest.mock import AsyncMock, patch


TRADE_PAYLOAD = {
    "symbol": "featured",
    "direction": "LONG",
    "entry_price": 105000.0,
    "stop_loss": 103500.0,
    "take_profit": 107000.0,
    "risk_percent": 1.0,
    "leverage": 10,
}


@pytest.mark.asyncio
async def test_create_trade(client, auth_headers):
    with patch(
        "app.routers.trades.ExchangeService.get_account_balance",
        new_callable=AsyncMock,
        return_value={"balance": 10000.0, "equity": 10000.0, "unrealized_pnl": 0.0,
                      "margin_used": 0.0, "free_margin": 10000.0},
    ):
        response = await client.post(
            "/api/v1/trades", json=TRADE_PAYLOAD, headers=auth_headers
        )
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "featured"
    assert data["direction"] == "LONG"
    assert data["status"] == "OPEN"
    assert data["quantity"] > 0


@pytest.mark.asyncio
async def test_get_open_trades(client, auth_headers):
    response = await client.get("/api/v1/trades/open", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_trade_history(client, auth_headers):
    response = await client.get("/api/v1/trades/history", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_invalid_risk_percent(client, auth_headers):
    payload = {**TRADE_PAYLOAD, "risk_percent": 15.0}
    with patch(
        "app.routers.trades.ExchangeService.get_account_balance",
        new_callable=AsyncMock,
        return_value={"balance": 10000.0, "equity": 10000.0, "unrealized_pnl": 0.0,
                      "margin_used": 0.0, "free_margin": 10000.0},
    ):
        response = await client.post("/api/v1/trades", json=payload, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_close_nonexistent_trade(client, auth_headers):
    response = await client.post(
        "/api/v1/trades/99999/close",
        json={"exit_price": 106000.0},
        headers=auth_headers,
    )
    assert response.status_code == 400
