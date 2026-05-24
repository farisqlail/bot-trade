import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_dashboard_returns_all_sections(client, auth_headers):
    with patch(
        "app.routers.dashboard.ExchangeService.get_account_balance",
        new_callable=AsyncMock,
        return_value={"balance": 10000.0, "equity": 10200.0, "unrealized_pnl": 200.0,
                      "margin_used": 500.0, "free_margin": 9700.0},
    ):
        response = await client.get("/api/v1/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "account" in data
    assert "pnl" in data
    assert "trades" in data
    assert "risk" in data
    assert "bot" in data
    assert "last_updated" in data


@pytest.mark.asyncio
async def test_dashboard_account_metrics(client, auth_headers):
    with patch(
        "app.routers.dashboard.ExchangeService.get_account_balance",
        new_callable=AsyncMock,
        return_value={"balance": 10000.0, "equity": 10200.0, "unrealized_pnl": 200.0,
                      "margin_used": 500.0, "free_margin": 9700.0},
    ):
        response = await client.get("/api/v1/dashboard", headers=auth_headers)

    account = response.json()["account"]
    assert account["balance"] == 10000.0
    assert account["equity"] == 10200.0


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client):
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 403
