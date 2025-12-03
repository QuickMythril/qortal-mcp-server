import pytest
from fastapi.testclient import TestClient

from qortal_mcp.server import app
from qortal_mcp.rate_limiter import PerKeyRateLimiter


@pytest.fixture
def client():
    return TestClient(app)


def test_health_route(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
    assert "X-Request-ID" in resp.headers


def test_mcp_initialize(client):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0.0.1"}},
    }
    resp = client.post("/mcp", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["protocolVersion"] == "2025-03-26"


def test_mcp_list_tools(client):
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["result"]["tools"], list)


def test_rate_limit_response(monkeypatch, client):
    # Force rate limiter to deny
    from qortal_mcp import server as srv

    class DenyLimiter:
        async def allow(self, _tool):
            return False

    monkeypatch.setattr(srv, "rate_limiter", DenyLimiter())
    resp = client.get("/tools/node_status")
    assert resp.status_code == 429
    assert resp.json()["error"]["message"] == "Rate limit exceeded"
