import pytest
from fastapi.testclient import TestClient

from qortal_mcp import server


@pytest.fixture
def client():
    return TestClient(server.app)


def test_account_overview_route(monkeypatch, client):
    async def fake_tool(address, include_assets=False, asset_ids=None):
        return {"address": address, "includeAssets": include_assets, "assetIds": asset_ids}

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "get_account_overview", fake_tool)
    resp = client.get("/tools/account_overview/Q" + "1" * 33 + "?include_assets=true&asset_ids=1&asset_ids=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["includeAssets"] is True
    assert body["assetIds"] == ["1", "2"] or body["assetIds"] == [1, 2]


def test_chat_messages_route_success(monkeypatch, client):
    async def fake_tool(**kwargs):
        return [{"signature": "s", "filters": kwargs}]

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "get_chat_messages", fake_tool)
    resp = client.get("/tools/chat/messages?txGroupId=1&decode_text=true")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["signature"] == "s"


def test_qdn_search_route_error(monkeypatch, client):
    async def fake_tool(*args, **kwargs):
        return {"error": "Invalid limit."}

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "search_qdn", fake_tool)
    resp = client.get("/tools/qdn_search")
    assert resp.status_code == 200
    assert resp.json()["error"] == "Invalid limit."


def test_trade_offers_route(monkeypatch, client):
    async def fake_tool(limit=None, offset=None, reverse=None, foreign_blockchain=None):
        return [{"tradeAddress": "A1"}]

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "list_trade_offers", fake_tool)
    resp = client.get("/tools/trade_offers?limit=2")
    assert resp.status_code == 200
    assert resp.json()[0]["tradeAddress"] == "A1"


def test_balance_route(monkeypatch, client):
    async def fake_tool(address, asset_id=0):
        return {"assetId": asset_id, "address": address}

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "get_balance", fake_tool)
    resp = client.get("/tools/balance/Q" + "1" * 33 + "?assetId=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["assetId"] == 5


def test_chat_count_route(monkeypatch, client):
    async def fake_tool(**kwargs):
        return {"count": 2}

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "count_chat_messages", fake_tool)
    resp = client.get("/tools/chat/messages/count?involving=Q" + "1" * 33 + "&involving=Q" + "2" * 33)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2
