import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.tools.blocks import (
    get_block_at_timestamp,
    get_block_height,
    get_block_by_height,
    list_block_summaries,
    list_block_range,
)
from qortal_mcp.tools.blocks_extra import (
    get_block_by_signature,
    get_block_height_by_signature,
    get_first_block,
    get_last_block,
)
from qortal_mcp.tools.transactions import search_transactions
from qortal_mcp.tools.transactions_extra import (
    get_transaction_by_signature,
    get_transaction_by_reference,
    list_transactions_by_block,
    list_transactions_by_address,
    list_transactions_by_creator,
)
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
async def test_block_height_success_and_api_error():
    class StubClient:
        async def fetch_block_height(self):
            return 7

    assert await get_block_height(client=StubClient()) == {"height": 7}

    class ApiClient:
        async def fetch_block_height(self):
            raise QortalApiError("fail")

    assert await get_block_height(client=ApiClient()) == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_block_summaries_invalid_params():
    assert await list_block_summaries(start="a", end=1) == {"error": "Invalid start or end height."}
    assert await list_block_summaries(start=1, end="b") == {"error": "Invalid start or end height."}


@pytest.mark.asyncio
async def test_block_summaries_success_and_unexpected():
    class StubClient:
        async def fetch_block_summaries(self, **kwargs):
            return [{"height": kwargs["start"]}]

    result = await list_block_summaries(start=1, end=2, client=StubClient())
    assert result == [{"height": 1}]

    class UnexpectedClient:
        async def fetch_block_summaries(self, **kwargs):
            return {"not": "list"}

    assert await list_block_summaries(start=1, end=2, client=UnexpectedClient()) == {"error": "Unexpected response from node."}


@pytest.mark.asyncio
async def test_block_range_invalid():
    assert await list_block_range(height="x", count=1) == {"error": "Invalid height."}
    assert await list_block_range(height=1, count="x") == {"error": "Invalid count."}


@pytest.mark.asyncio
async def test_block_range_node_unreachable():
    class FailClient:
        async def fetch_block_range(self, **kwargs):
            raise NodeUnreachableError("down")

    result = await list_block_range(height=1, count=1, client=FailClient())
    assert result == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_block_summaries_unauthorized():
    class FailClient:
        async def fetch_block_summaries(self, **kwargs):
            raise UnauthorizedError("nope")

    result = await list_block_summaries(start=1, end=2, client=FailClient())
    assert result == {"error": "Unauthorized or API key required."}


@pytest.mark.asyncio
async def test_block_at_timestamp_success():
    class StubClient:
        async def fetch_block_at_timestamp(self, ts):
            return {"height": 10, "timestamp": ts}

    result = await get_block_at_timestamp(5, client=StubClient())
    assert result["height"] == 10


@pytest.mark.asyncio
async def test_list_block_range_success():
    captured = {}

    class StubClient:
        async def fetch_block_range(self, **kwargs):
            captured.update(kwargs)
            return [{"height": 1}, {"height": 2}]

    cfg = QortalConfig(default_block_range=1, max_block_range=2)
    result = await list_block_range(height=5, count=5, reverse=True, include_online_signatures=True, client=StubClient(), config=cfg)
    assert len(result) == 2
    assert captured["reverse"] is True
    assert captured["include_online_signatures"] is True


@pytest.mark.asyncio
async def test_block_range_success_and_unauthorized():
    captured = {}

    class StubClient:
        async def fetch_block_range(self, **kwargs):
            captured.update(kwargs)
            return [{"height": 1}, {"height": 2}, {"height": 3}, {"height": 4}]

    cfg = QortalConfig(default_block_range=2, max_block_range=3)
    result = await list_block_range(height=5, count=10, reverse=True, include_online_signatures=False, client=StubClient(), config=cfg)
    assert captured["reverse"] is True
    assert captured["include_online_signatures"] is False
    assert len(result) == 3

    class UnauthorizedClient:
        async def fetch_block_range(self, **kwargs):
            raise UnauthorizedError("nope")

    assert await list_block_range(height=1, count=1, client=UnauthorizedClient()) == {"error": "Unauthorized or API key required."}


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


@pytest.mark.asyncio
async def test_block_by_signature_requires_sig():
    assert await get_block_by_signature("") == {"error": "Signature is required."}
    assert await get_block_by_signature("notbase58!") == {"error": "Invalid signature."}


@pytest.mark.asyncio
async def test_block_height_by_signature_requires_sig():
    assert await get_block_height_by_signature("") == {"error": "Signature is required."}
    assert await get_block_height_by_signature("notbase58!") == {"error": "Invalid signature."}


@pytest.mark.asyncio
async def test_first_last_block_errors():
    class StubClient:
        async def fetch_first_block(self):
            raise NodeUnreachableError("down")

    assert await get_first_block(client=StubClient()) == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_tx_by_signature_requires_sig():
    assert await get_transaction_by_signature("") == {"error": "Signature is required."}


@pytest.mark.asyncio
async def test_tx_by_reference_requires_ref():
    assert await get_transaction_by_reference("") == {"error": "Reference is required."}


@pytest.mark.asyncio
async def test_txs_by_block_requires_sig():
    assert await list_transactions_by_block("") == {"error": "Signature is required."}
    assert await list_transactions_by_block("notbase58!") == {"error": "Invalid signature."}


@pytest.mark.asyncio
async def test_txs_by_block_forwards_params_and_clamps():
    captured: dict[str, object] = {}

    class StubClient:
        async def fetch_transactions_by_block(self, sig, **kwargs):
            captured["sig"] = sig
            captured.update(kwargs)
            return []

    await list_transactions_by_block("A" * 44, limit=500, offset=5, reverse=True, client=StubClient())
    assert captured["sig"] == "A" * 44
    assert captured["limit"] == 100
    assert captured["offset"] == 5
    assert captured["reverse"] is True


@pytest.mark.asyncio
async def test_txs_by_address_invalid():
    assert await list_transactions_by_address("bad") == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_txs_by_creator_invalid_key():
    assert await list_transactions_by_creator("bad") == {"error": "Invalid public key."}
    assert await list_transactions_by_creator("6nHvEmQJ52LaoYxCxu32cLRbp394ziKET6rkh7F5Cyok") == {
        "error": "confirmationStatus is required."
    }


@pytest.mark.asyncio
async def test_txs_by_creator_invalid_key_from_core():
    class StubClient:
        async def fetch_transactions_by_creator(self, *args, **kwargs):
            raise QortalApiError("bad", code="INVALID_PUBLIC_KEY")

    result = await list_transactions_by_creator(
        "QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", confirmation_status="CONFIRMED", client=StubClient()
    )
    assert result == {"error": "Invalid public key."}


@pytest.mark.asyncio
async def test_block_at_timestamp_block_unknown():
    class StubClient:
        async def fetch_block_at_timestamp(self, ts):
            raise QortalApiError("block", code="BLOCK_UNKNOWN", status_code=404)

    result = await get_block_at_timestamp(0, client=StubClient())
    assert result == {"error": "No block at or before timestamp."}
