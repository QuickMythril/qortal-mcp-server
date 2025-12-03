import pytest
from fastapi.testclient import TestClient

from qortal_mcp.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_validate_address_route(client):
    resp = client.get("/tools/validate_address/bad")
    assert resp.status_code == 200
    assert resp.json() == {"isValid": False}


def test_rate_limit_mcp_list_tools(client, monkeypatch):
    # Force rate limiter to deny.
    from qortal_mcp import server as server_mod

    async def deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr(server_mod.rate_limiter, "allow", deny)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "list_tools"})
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["message"] == "Rate limit exceeded"


def test_metrics_increments_requests(client):
    resp = client.get("/tools/validate_address/bad")
    assert resp.status_code == 200
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    data = metrics_resp.json()
    assert data.get("requests", 0) >= 2  # validate + metrics


def test_metrics_rate_limited_increment(client, monkeypatch):
    from qortal_mcp import server as server_mod

    async def deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr(server_mod.rate_limiter, "allow", deny)
    client.get("/tools/node_info")
    data = client.get("/metrics").json()
    assert data.get("rate_limited", 0) >= 1


def test_trade_offers_route_normalizes_fields(client, monkeypatch):
    from qortal_mcp import server as server_mod
    from qortal_mcp.tools import trade as trade_mod

    class StubClient:
        async def fetch_trade_offers(self, *, limit: int, **kwargs):
            return [
                {
                    "qortalCreatorTradeAddress": "QT123",
                    "qortalAtAddress": "AT456",
                    "qortalCreator": "QCREATOR",
                    "creationTimestamp": 42,
                    "foreignBlockchain": "DOGE",
                    "expectedForeignAmount": "1.5",
                    "qortAmount": "10",
                }
            ]

    async def fake_list_trade_offers(*, limit=None, client=None, config=None):
        return await trade_mod.list_trade_offers(limit=limit, client=StubClient(), config=config or trade_mod.default_config)

    monkeypatch.setattr(server_mod, "list_trade_offers", fake_list_trade_offers)
    resp = client.get("/tools/trade_offers")
    assert resp.status_code == 200
    offers = resp.json()
    assert offers[0]["tradeAddress"] == "AT456"
    assert offers[0]["creator"] == "QCREATOR"
    assert offers[0]["foreignCurrency"] == "DOGE"
    assert offers[0]["timestamp"] == 42
    assert offers[0]["offeringQort"] == "10"
    assert offers[0]["expectedForeign"] == "1.5"
