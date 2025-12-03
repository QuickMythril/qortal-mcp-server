import pytest

from qortal_mcp.tools.trade import (
    get_trade_price,
    get_trade_ledger,
    list_hidden_trade_offers,
    get_trade_detail,
    list_completed_trades,
)
from qortal_mcp.qortal_api import AddressNotFoundError, NodeUnreachableError, QortalApiError, UnauthorizedError
from qortal_mcp.config import QortalConfig


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

    class UnauthorizedClient:
        async def fetch_trade_price(self, *, blockchain: str, max_trades=None, inverse=None):
            raise UnauthorizedError("nope")

    assert await get_trade_price(blockchain="BITCOIN", client=UnauthorizedClient()) == {"error": "Unauthorized or API key required."}


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


@pytest.mark.asyncio
async def test_list_hidden_trade_offers_validation_and_errors():
    assert await list_hidden_trade_offers(foreign_blockchain="invalid") == {"error": "Invalid foreign blockchain."}

    class UnauthorizedClient:
        async def fetch_hidden_trade_offers(self, **kwargs):
            raise UnauthorizedError("nope")

    assert await list_hidden_trade_offers(client=UnauthorizedClient()) == {"error": "Unauthorized or API key required."}

    class SuccessClient:
        async def fetch_hidden_trade_offers(self, **kwargs):
            return [
                {"qortalAtAddress": "A1", "expectedForeignAmount": 2, "foreignBlockchain": "BITCOIN"},
                {"atAddress": "A2", "expectedForeign": 3, "foreignCurrency": "LITECOIN"},
            ]

    offers = await list_hidden_trade_offers(limit=1, client=SuccessClient(), config=QortalConfig(default_trade_offers=5, max_trade_offers=5))
    assert len(offers) == 1
    assert offers[0]["tradeAddress"] == "A1"


@pytest.mark.asyncio
async def test_get_trade_detail_validation_and_errors():
    assert await get_trade_detail(at_address="") == {"error": "AT address is required."}
    assert await get_trade_detail(at_address="bad") == {"error": "Invalid AT address."}

    class NotFoundClient:
        async def fetch_trade_detail(self, *_args, **_kwargs):
            raise AddressNotFoundError("missing")

    assert await get_trade_detail(at_address="A" * 34, client=NotFoundClient()) == {"error": "Trade not found."}

    class ApiNotFoundClient:
        async def fetch_trade_detail(self, *_args, **_kwargs):
            raise QortalApiError("nope", status_code=404)

    assert await get_trade_detail(at_address="A" * 34, client=ApiNotFoundClient()) == {"error": "Trade not found."}

    class SuccessClient:
        async def fetch_trade_detail(self, at_address):
            return {"atAddress": at_address, "expectedBitcoin": 5}

    result = await get_trade_detail(at_address="A" * 34, client=SuccessClient())
    assert result["tradeAddress"] == "A" * 34
    assert result["expectedForeign"] == "5"


@pytest.mark.asyncio
async def test_list_completed_trades_validation_and_success():
    assert await list_completed_trades(minimum_timestamp="bad") == {"error": "Invalid minimumTimestamp."}
    assert await list_completed_trades(buyer_public_key="short") == {"error": "Invalid public key."}

    class UnauthorizedClient:
        async def fetch_completed_trades(self, **kwargs):
            raise UnauthorizedError("nope")

    assert await list_completed_trades(client=UnauthorizedClient()) == {"error": "Unauthorized or API key required."}

    class SuccessClient:
        async def fetch_completed_trades(self, **kwargs):
            return [
                {
                    "qortalAtAddress": "A1",
                    "foreignBlockchain": "BITCOIN",
                    "tradeTimestamp": 1,
                    "qortAmount": 2,
                    "expectedForeignAmount": 3,
                    "mode": "SOME",
                },
                {
                    "atAddress": "A2",
                    "timestamp": 2,
                    "expectedForeign": 4,
                },
            ]

    trades = await list_completed_trades(
        limit=5,
        minimum_timestamp=100,
        buyer_public_key="A" * 44,
        seller_public_key="B" * 44,
        client=SuccessClient(),
        config=QortalConfig(default_trade_offers=2, max_trade_offers=2),
    )
    assert len(trades) == 2
    assert trades[0]["tradeAddress"] == "A1"
