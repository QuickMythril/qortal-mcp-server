import json

import pytest
from fastapi.testclient import TestClient

from qortal_mcp.server import app
from qortal_mcp.metrics import default_metrics
from qortal_mcp.qortal_api.client import QortalApiClient


def test_request_ids_on_routes_and_mcp():
    client = TestClient(app)
    resp = client.get("/tools/validate_address/bad")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers

    rpc = client.post("/mcp", json={"jsonrpc": "2.0", "id": 99, "method": "list_tools"})
    assert rpc.status_code == 200
    body = rpc.json()
    assert body.get("requestId")
    assert body.get("id") == 99


def test_rate_limit_increments_metrics(monkeypatch):
    client = TestClient(app)

    # Force limiter to deny
    from qortal_mcp import server as server_mod

    async def deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr(server_mod.rate_limiter, "allow", deny)

    resp = client.get("/tools/node_status")
    assert resp.status_code == 429

    metrics_resp = client.get("/metrics")
    data = metrics_resp.json()
    assert data.get("rate_limited", 0) >= 1
    # tool_error counter should not increment on rate limit
    assert data.get("tool_error", {}).get("get_node_status", 0) == 0


@pytest.mark.asyncio
async def test_api_key_header_is_sent(monkeypatch):
    sent_headers = {}

    class HeaderCaptureClient:
        async def get(self, path, params=None, headers=None):
            sent_headers.update(headers or {})
            return type("Resp", (), {"status_code": 200, "json": lambda self: {}})()

        async def aclose(self):
            return None

    monkeypatch.setenv("QORTAL_API_KEY", "secret-key")
    from importlib import reload
    import qortal_mcp.config as cfg

    reload(cfg)
    from qortal_mcp.qortal_api.client import QortalApiClient

    client = QortalApiClient(config=cfg.default_config, async_client=HeaderCaptureClient())
    await client.fetch_node_status()
    assert sent_headers.get("X-API-KEY") == "secret-key"

