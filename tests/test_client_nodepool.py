import pytest

import httpx

from qortal_mcp.config import QortalConfig
from qortal_mcp.qortal_api.client import (
    NodeUnreachableError,
    QortalApiClient,
    UnauthorizedError,
)


class DummyResponse:
    def __init__(self, status_code: int, json_data=None, text: str = ""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class DummyAsyncClient:
    def __init__(self, base_url: str, timeout: float, behavior):
        self.base_url = base_url
        self.timeout = timeout
        self._behavior = behavior

    async def get(self, path, params=None, headers=None):
        return self._behavior(self.base_url, path, params or {}, headers or {})

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_nodepool_fallback_success(monkeypatch):
    calls = []

    def behavior(base_url, path, params, headers):
        calls.append((base_url, headers))
        if base_url == "http://primary":
            raise httpx.RequestError("primary down")
        return DummyResponse(200, {"ok": True})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda base_url, timeout: DummyAsyncClient(base_url, timeout, behavior),
    )

    cfg = QortalConfig(
        base_url="http://primary",
        public_nodes=["http://fallback"],
        allow_public_fallback=True,
        api_key="secret",
    )
    client = QortalApiClient(config=cfg)

    result = await client.fetch_node_status()
    assert result == {"ok": True}

    assert calls[0][0] == "http://primary"
    assert calls[1][0] == "http://fallback"
    assert calls[0][1].get("X-API-KEY") == "secret"
    assert "X-API-KEY" not in calls[1][1]

    await client.aclose()


@pytest.mark.asyncio
async def test_nodepool_all_nodes_unreachable(monkeypatch):
    def behavior(base_url, path, params, headers):
        raise httpx.RequestError(f"{base_url} down")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda base_url, timeout: DummyAsyncClient(base_url, timeout, behavior),
    )

    cfg = QortalConfig(
        base_url="http://primary",
        public_nodes=["http://fallback"],
        allow_public_fallback=True,
    )
    client = QortalApiClient(config=cfg)

    with pytest.raises(NodeUnreachableError):
        await client.fetch_node_status()

    await client.aclose()


@pytest.mark.asyncio
async def test_nodepool_admin_unauthorized_on_fallback(monkeypatch):
    calls = []

    def behavior(base_url, path, params, headers):
        calls.append((base_url, headers))
        if base_url == "http://primary":
            raise httpx.RequestError("primary down")
        return DummyResponse(401, {"error": "Unauthorized"})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda base_url, timeout: DummyAsyncClient(base_url, timeout, behavior),
    )

    cfg = QortalConfig(
        base_url="http://primary",
        public_nodes=["http://fallback"],
        allow_public_fallback=True,
        api_key="secret",
    )
    client = QortalApiClient(config=cfg)

    with pytest.raises(UnauthorizedError):
        await client.fetch_node_status()

    assert calls[-1][0] == "http://fallback"
    assert "X-API-KEY" not in calls[-1][1]

    await client.aclose()
