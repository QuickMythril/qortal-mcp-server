import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.tools.qdn import search_qdn
from qortal_mcp.tools.trade import list_trade_offers
from qortal_mcp.qortal_api import UnauthorizedError


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
        async def search_qdn(self, *, address=None, service=None, limit=None):
            # Return more than the allowed max to verify truncation.
            return [{"signature": str(i), "publisher": "Q...", "service": 1, "timestamp": i} for i in range(30)]

    custom_config = QortalConfig(max_qdn_results=5, default_qdn_results=2)
    results = await search_qdn(address="QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", limit=50, client=StubClient(), config=custom_config)
    assert isinstance(results, list)
    assert len(results) == 5
    assert results[0]["signature"] == "0"
