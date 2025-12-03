import pytest

from qortal_mcp.tools.trade import get_trade_price, get_trade_ledger
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError


@pytest.mark.asyncio
async def test_get_trade_price_validation_and_errors():
    result = await get_trade_price(blockchain="")
    assert result == {"error": "Blockchain is required."}

    class StubClient:
        async def fetch_trade_price(self, *, blockchain: str, max_trades=None, inverse=None):
            return {"price": "1.0"}

    price = await get_trade_price(blockchain="BITCOIN", max_trades=1, client=StubClient())
    assert isinstance(price, dict)

    class FailClient:
        async def fetch_trade_price(self, *, blockchain: str, max_trades=None, inverse=None):
            raise NodeUnreachableError("down")

    assert await get_trade_price(blockchain="BITCOIN", client=FailClient()) == {"error": "Node unreachable"}

    class ApiErrorClient:
        async def fetch_trade_price(self, *, blockchain: str, max_trades=None, inverse=None):
            raise QortalApiError("fail")

    assert await get_trade_price(blockchain="BITCOIN", client=ApiErrorClient()) == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_get_trade_ledger_validation_and_errors():
    result = await get_trade_ledger(public_key="")
    assert result == {"error": "Public key is required."}

    class StubClient:
        async def fetch_trade_ledger(self, *, public_key: str, minimum_timestamp=None):
            return "csv"

    ledger = await get_trade_ledger(public_key="A" * 44, client=StubClient())
    assert ledger == {"ledger": "csv"}

    class FailClient:
        async def fetch_trade_ledger(self, *, public_key: str, minimum_timestamp=None):
            raise NodeUnreachableError("down")

    assert await get_trade_ledger(public_key="A" * 44, client=FailClient()) == {"error": "Node unreachable"}
