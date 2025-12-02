import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.tools.qdn import search_qdn
from qortal_mcp.tools.trade import list_trade_offers
from qortal_mcp.qortal_api import UnauthorizedError
from qortal_mcp.qortal_api.client import NodeUnreachableError, QortalApiError


@pytest.mark.asyncio
async def test_list_trade_offers_clamps_limit():
    class StubClient:
        async def fetch_trade_offers(self, *, limit: int):
            return [{"tradeAddress": f"addr-{i}"} for i in range(30)]

    # Clamp to config.max_trade_offers (5) even if caller requests more.
    custom_config = QortalConfig(max_trade_offers=5, default_trade_offers=3)
    result = await list_trade_offers(limit=50, client=StubClient(), config=custom_config)
    assert isinstance(result, list)
    assert len(result) == 5


@pytest.mark.asyncio
async def test_list_trade_offers_unauthorized_error():
    class StubClient:
        async def fetch_trade_offers(self, *, limit: int):
            raise UnauthorizedError("Unauthorized", status_code=401)

    result = await list_trade_offers(client=StubClient())
    assert result == {"error": "Unauthorized or API key required."}


@pytest.mark.asyncio
async def test_list_trade_offers_normalizes_core_fields():
    core_style_offer = {
        "qortalCreatorTradeAddress": "QT123",
        "qortalAtAddress": "AT456",
        "qortalCreator": "QCREATOR",
        "creationTimestamp": 1234567890,
        "foreignBlockchain": "LTC",
        "expectedForeignAmount": "0.1",
        "qortAmount": "5",
    }

    class StubClient:
        async def fetch_trade_offers(self, *, limit: int):
            return [core_style_offer]

    offers = await list_trade_offers(client=StubClient())
    assert offers == [
        {
            "tradeAddress": "QT123",
            "creator": "QCREATOR",
            "offeringQort": "5",
            "expectedForeign": "0.1",
            "foreignCurrency": "LTC",
            "mode": None,
            "timestamp": 1234567890,
        }
    ]


@pytest.mark.asyncio
async def test_list_trade_offers_skips_non_dict_and_handles_unreachable():
    class StubClient:
        calls = 0

        async def fetch_trade_offers(self, *, limit: int):
            StubClient.calls += 1
            if StubClient.calls == 1:
                return ["not-a-dict"]
            raise NodeUnreachableError("down")

    # First call should skip invalid entry and return empty list
    offers = await list_trade_offers(client=StubClient())
    assert offers == []
    # Second call triggers unreachable error mapping
    offers = await list_trade_offers(client=StubClient())
    assert offers == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_list_trade_offers_api_error():
    class StubClient:
        async def fetch_trade_offers(self, *, limit: int):
            raise QortalApiError("fail")

    offers = await list_trade_offers(client=StubClient())
    assert offers == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_list_trade_offers_unexpected_error():
    class StubClient:
        async def fetch_trade_offers(self, *, limit: int):
            raise Exception("boom")

    offers = await list_trade_offers(client=StubClient())
    assert offers == {"error": "Unexpected error while retrieving trade offers."}


@pytest.mark.asyncio
async def test_qdn_requires_address_or_service():
    result = await search_qdn()
    assert result == {"error": "At least one of address or service is required."}


@pytest.mark.asyncio
async def test_qdn_invalid_address():
    result = await search_qdn(address="bad")
    assert result == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_qdn_clamps_limit_and_maps_results():
    class StubClient:
        async def search_qdn(self, *, address=None, service=None, limit=None, **kwargs):
            # Return more than the allowed max to verify truncation.
            return [{"signature": str(i), "service": "WEBSITE", "timestamp": i} for i in range(30)]

    custom_config = QortalConfig(max_qdn_results=5, default_qdn_results=2)
    results = await search_qdn(address="QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", limit=50, client=StubClient(), config=custom_config, start_block=1, block_limit=10)
    assert isinstance(results, list)
    assert len(results) == 5
    assert results[0]["signature"] == "0"


@pytest.mark.asyncio
async def test_name_normalization_defaults_sale_flags():
    raw_entry = {
        "name": "abc",
        "owner": "Q",
        "data": "x",
        "registeredWhen": 1,
        "updatedWhen": 2,
    }
    normalized = qortal_mcp.tools.names._normalize_name_entry(raw_entry, 100)  # type: ignore[attr-defined]
    assert normalized["isForSale"] is False
    assert normalized["salePrice"] is None


@pytest.mark.asyncio
async def test_qdn_invalid_service_code():
    result = await search_qdn(service="not-int")
    assert result == {"error": "Invalid service code or name."}
    result = await search_qdn(service=-1)
    assert result == {"error": "Invalid service code or name."}


@pytest.mark.asyncio
async def test_qdn_service_only_ok():
    class StubClient:
        async def search_qdn(self, *, address=None, service=None, limit=None, **kwargs):
            return [{"signature": "s", "service": service, "timestamp": 1}]

    result = await search_qdn(service=1, start_block=1, block_limit=10, client=StubClient())
    assert result and result[0]["service"] == 1


@pytest.mark.asyncio
async def test_qdn_address_and_service_ok():
    class StubClient:
        async def search_qdn(self, *, address=None, service=None, limit=None, **kwargs):
            return [{"signature": "s", "service": service, "timestamp": 1}]

    result = await search_qdn(address="QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", service=1, start_block=1, block_limit=10, client=StubClient())
    assert result and result[0]["service"] == 1


@pytest.mark.asyncio
async def test_qdn_node_unreachable():
    class StubClient:
        async def search_qdn(self, *, address=None, service=None, limit=None, **kwargs):
            raise NodeUnreachableError("down")

    result = await search_qdn(address="QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_qdn_unexpected_error():
    class StubClient:
        async def search_qdn(self, *, address=None, service=None, limit=None, **kwargs):
            raise QortalApiError("boom")

    result = await search_qdn(address="QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_qdn_unauthorized():
    class StubClient:
        async def search_qdn(self, *, address=None, service=None, limit=None, **kwargs):
            raise UnauthorizedError("nope")

    result = await search_qdn(address="QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Unauthorized or API key required."}
