import pytest

from qortal_mcp.qortal_api.client import QortalApiClient


class CaptureClient:
    def __init__(self, json_body):
        self.calls = []
        self._json_body = json_body

    async def get(self, path, params=None, headers=None):
        self.calls.append({"path": path, "params": params, "headers": headers})

        class Resp:
            status_code = 200

            def __init__(self, body):
                self._body = body

            def json(self):
                return self._body

        return Resp(self._json_body)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_fetch_names_by_owner_path_and_params():
    client = QortalApiClient(async_client=CaptureClient(["name1"]))
    result = await client.fetch_names_by_owner("Q addr", limit=2, offset=1, reverse=True)
    assert result == ["name1"]
    call = client._client.calls[0]
    assert "/names/address/" in call["path"]
    assert call["params"] == {"limit": 2, "offset": 1, "reverse": True}


@pytest.mark.asyncio
async def test_fetch_trade_offers_passes_limit():
    client = QortalApiClient(async_client=CaptureClient([{"offer": 1}]))
    result = await client.fetch_trade_offers(limit=5)
    assert result == [{"offer": 1}]
    call = client._client.calls[0]
    assert call["params"] == {"limit": 5}


@pytest.mark.asyncio
async def test_search_qdn_passes_filters():
    client = QortalApiClient(async_client=CaptureClient([{"signature": "s"}]))
    result = await client.search_qdn(address="Q1", service=2, limit=3)
    assert result == [{"signature": "s"}]
    call = client._client.calls[0]
    assert call["params"] == {"address": "Q1", "service": 2, "limit": 3}


@pytest.mark.asyncio
async def test_fetch_all_names_and_forsale_params():
    client = QortalApiClient(async_client=CaptureClient([{"name": "a"}]))
    result = await client.fetch_all_names(after=1, limit=2, offset=3, reverse=True)
    assert result == [{"name": "a"}]
    call = client._client.calls[0]
    assert call["params"] == {"after": 1, "limit": 2, "offset": 3, "reverse": True}

    client = QortalApiClient(async_client=CaptureClient([{"name": "sale"}]))
    result = await client.fetch_names_for_sale(limit=1, offset=2, reverse=True)
    assert result == [{"name": "sale"}]
    call = client._client.calls[0]
    assert call["params"] == {"limit": 1, "offset": 2, "reverse": True}
