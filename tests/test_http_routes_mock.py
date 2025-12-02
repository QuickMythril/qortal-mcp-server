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
    assert resp.json()["error"] == "Rate limit exceeded"


def test_metrics_increments_requests(client):
    resp = client.get("/tools/validate_address/bad")
    assert resp.status_code == 200
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    data = metrics_resp.json()
    assert data.get("requests", 0) >= 2  # validate + metrics
