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


def test_name_routes(monkeypatch, client):
    async def names_by_address(address, **kwargs):
        return [{"name": "demo", "owner": address}]

    async def primary_name(address):
        return {"name": "primary"}

    async def search_names(query, **kwargs):
        return [{"name": query}]

    async def list_names(**kwargs):
        return [{"name": "n"}]

    async def list_names_for_sale(**kwargs):
        return [{"name": "for-sale"}]

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "get_names_by_address", names_by_address)
    monkeypatch.setattr(server, "get_primary_name", primary_name)
    monkeypatch.setattr(server, "search_names", search_names)
    monkeypatch.setattr(server, "list_names", list_names)
    monkeypatch.setattr(server, "list_names_for_sale", list_names_for_sale)

    resp = client.get("/tools/names_by_address/Q" + "1" * 33)
    assert resp.status_code == 200 and resp.json()[0]["owner"].startswith("Q")
    assert client.get("/tools/primary_name/Q" + "1" * 33).json()["name"] == "primary"
    assert client.get("/tools/search_names?query=test").json()[0]["name"] == "test"
    assert client.get("/tools/list_names").json()[0]["name"] == "n"
    assert client.get("/tools/list_names_for_sale").json()[0]["name"] == "for-sale"


def test_group_and_trade_routes(monkeypatch, client):
    async def group_members(group_id, **kwargs):
        return [{"member": "Q" * 34, "group": group_id}]

    async def group_invites_by_address(address):
        return [{"groupId": 1, "invitee": address}]

    async def hidden_offers(**kwargs):
        return [{"tradeAddress": "A1"}]

    async def chat_message(signature, **kwargs):
        return {"signature": signature}

    async def active_chats(address, **kwargs):
        return {"direct": [{"address": address}]}

    async def qdn_search(**kwargs):
        return [{"name": "item"}]

    async def account_overview(address, include_assets=False, asset_ids=None):
        return {"address": address, "assets": asset_ids if include_assets else []}

    async def no_limit(_tool):
        return None

    monkeypatch.setattr(server, "_enforce_rate_limit", no_limit)
    monkeypatch.setattr(server, "get_group_members", group_members)
    monkeypatch.setattr(server, "get_group_invites_by_address", group_invites_by_address)
    monkeypatch.setattr(server, "list_hidden_trade_offers", hidden_offers)
    monkeypatch.setattr(server, "get_chat_message_by_signature", chat_message)
    monkeypatch.setattr(server, "get_active_chats", active_chats)
    monkeypatch.setattr(server, "search_qdn", qdn_search)
    monkeypatch.setattr(server, "get_account_overview", account_overview)

    assert client.get("/tools/group/1/members").json()[0]["group"] == 1
    assert client.get("/tools/group_invites/address/Q" + "1" * 33).json()[0]["groupId"] == 1
    assert client.get("/tools/hidden_trade_offers").json()[0]["tradeAddress"] == "A1"
    assert client.get("/tools/chat/message/sig123").json()["signature"] == "sig123"
    assert client.get("/tools/chat/active/Q" + "1" * 33).json()["direct"][0]["address"].startswith("Q")
    assert client.get("/tools/qdn_search").json()[0]["name"] == "item"
    assets_out = client.get("/tools/account_overview/Q" + "1" * 33 + "?include_assets=true&asset_ids=7").json()["assets"]
    assert assets_out in ([7], ["7"])
