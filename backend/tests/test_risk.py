import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_risk_status(client, auth_headers):
    with patch(
        "app.routers.risk.ExchangeService.get_account_balance",
        new_callable=AsyncMock,
        return_value={"balance": 10000.0, "equity": 10000.0, "unrealized_pnl": 0.0,
                      "margin_used": 0.0, "free_margin": 10000.0},
    ):
        response = await client.get("/api/v1/risk/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["SAFE", "WARNING", "DANGER", "CRITICAL", "UNKNOWN"]


@pytest.mark.asyncio
async def test_get_risk_events(client, auth_headers):
    response = await client.get("/api/v1/risk/events", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_risk_status_safe_with_no_trades(client, auth_headers):
    with patch(
        "app.routers.risk.ExchangeService.get_account_balance",
        new_callable=AsyncMock,
        return_value={"balance": 10000.0, "equity": 10000.0, "unrealized_pnl": 0.0,
                      "margin_used": 0.0, "free_margin": 10000.0},
    ):
        response = await client.get("/api/v1/risk/status", headers=auth_headers)
    data = response.json()
    assert data["daily_loss_percent"] == 0.0
    assert data["consecutive_losses"] == 0
