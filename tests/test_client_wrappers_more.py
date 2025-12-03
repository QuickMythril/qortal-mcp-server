import pytest

from qortal_mcp.qortal_api.client import QortalApiClient


class MockResponse:
    def __init__(self, status_code: int, json_body=None, text_body: str | None = None):
        self.status_code = status_code
        self._json = json_body
        self.text = text_body or ""

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class MockAsyncClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, path, params=None, headers=None):
        if not self.responses:
            raise RuntimeError("No responses left")
        self.calls.append({"path": path, "params": params, "headers": headers})
        return self.responses.pop(0)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_wrapper_methods_success_paths():
    responses = [
        MockResponse(200, json_body=[{"name": "alice"}]),  # fetch_names_by_owner
        MockResponse(200, json_body=[{"name": "sale"}]),  # fetch_names_for_sale
        MockResponse(200, json_body={"name": "primary"}),  # fetch_primary_name
        MockResponse(200, json_body=[{"qortalAtAddress": "A1"}]),  # fetch_trade_offers
        MockResponse(200, json_body=[{"height": 1}]),  # fetch_block_summaries
        MockResponse(200, json_body=[{"height": 2}]),  # fetch_block_range
        MockResponse(200, json_body=[{"signature": "s"}]),  # search_transactions
        MockResponse(200, json_body=[{"assetId": 1, "assetBalance": "1"}]),  # fetch_asset_balances
        MockResponse(200, json_body=[{"name": "qdn"}]),  # search_qdn
        MockResponse(200, json_body=[{"data": "d"}]),  # fetch_chat_messages
        MockResponse(200, json_body=None, text_body="3"),  # count_chat_messages (text)
        MockResponse(200, json_body={"data": "d"}),  # fetch_chat_message
        MockResponse(200, json_body={"direct": [{"address": "Q" * 34}]}),  # fetch_active_chats
        MockResponse(200, json_body=[{"groupId": 1}]),  # fetch_groups
    ]
    mac = MockAsyncClient(responses)
    client = QortalApiClient(async_client=mac)

    assert await client.fetch_names_by_owner("Q" * 34) == [{"name": "alice"}]
    assert await client.fetch_names_for_sale() == [{"name": "sale"}]
    assert await client.fetch_primary_name("Q" * 34) == {"name": "primary"}
    offers = await client.fetch_trade_offers(limit=5)
    assert offers[0]["qortalAtAddress"] == "A1"
    assert await client.fetch_block_summaries(start=1, end=2) == [{"height": 1}]
    assert await client.fetch_block_range(height=1, count=1) == [{"height": 2}]
    assert await client.search_transactions() == [{"signature": "s"}]
    assert await client.fetch_asset_balances(limit=1) == [{"assetId": 1, "assetBalance": "1"}]
    assert await client.search_qdn(limit=1) == [{"name": "qdn"}]
    assert await client.fetch_chat_messages(limit=1) == [{"data": "d"}]
    assert await client.count_chat_messages(limit=1) == 3
    assert await client.fetch_chat_message("sig") == {"data": "d"}
    assert await client.fetch_active_chats("Q" * 34) == {"direct": [{"address": "Q" * 34}]}
    assert await client.fetch_groups() == [{"groupId": 1}]
