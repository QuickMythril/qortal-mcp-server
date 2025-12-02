import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.tools.blocks import (
    get_block_at_timestamp,
    get_block_height,
    get_block_by_height,
    list_block_summaries,
    list_block_range,
)
from qortal_mcp.tools.transactions import search_transactions
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError, UnauthorizedError, InvalidAddressError


@pytest.mark.asyncio
async def test_block_timestamp_invalid():
    assert await get_block_at_timestamp("bad") == {"error": "Invalid timestamp."}


@pytest.mark.asyncio
async def test_block_height_unreachable():
    class StubClient:
        async def fetch_block_height(self):
            raise NodeUnreachableError("down")

    result = await get_block_height(client=StubClient())
    assert result == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_block_by_height_invalid():
    assert await get_block_by_height(-1) == {"error": "Invalid height."}


@pytest.mark.asyncio
async def test_block_summaries_invalid_params():
    assert await list_block_summaries(start="a", end=1) == {"error": "Invalid start or end height."}
    assert await list_block_summaries(start=1, end="b") == {"error": "Invalid start or end height."}


@pytest.mark.asyncio
async def test_block_range_invalid():
    assert await list_block_range(height="x", count=1) == {"error": "Invalid height."}
    assert await list_block_range(height=1, count="x") == {"error": "Invalid count."}


@pytest.mark.asyncio
async def test_search_transactions_invalid_status():
    result = await search_transactions(confirmation_status="maybe")
    assert result == {"error": "Invalid confirmation status."}


@pytest.mark.asyncio
async def test_search_transactions_block_range_requires_confirmed():
    result = await search_transactions(start_block=1, block_limit=10, confirmation_status="UNCONFIRMED")
    assert result == {"error": "Block range requires confirmationStatus=CONFIRMED."}


@pytest.mark.asyncio
async def test_search_transactions_invalid_address():
    result = await search_transactions(address="bad", tx_types=["PAYMENT"])
    assert result == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_search_transactions_enforces_limit_rule():
    config = QortalConfig(max_tx_search=20, default_tx_search=20)
    result = await search_transactions(limit=50, config=config)
    assert result == {"error": "txType or address is required when limit exceeds 20."}


@pytest.mark.asyncio
async def test_search_transactions_client_errors():
    class StubClient:
        async def search_transactions(self, **kwargs):
            raise InvalidAddressError("bad")

    result = await search_transactions(address="QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", tx_types=["PAYMENT"], client=StubClient())
    assert result == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_search_transactions_success():
    class StubClient:
        async def search_transactions(self, **kwargs):
            return [{"signature": "s"}]

    result = await search_transactions(tx_types=["PAYMENT"], client=StubClient())
    assert isinstance(result, list)
    assert result[0]["signature"] == "s"
