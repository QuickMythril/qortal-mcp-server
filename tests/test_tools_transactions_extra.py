import pytest

from qortal_mcp.tools.transactions_extra import (
    get_transaction_by_signature,
    get_transaction_by_reference,
    list_transactions_by_block,
    list_transactions_by_address,
    list_transactions_by_creator,
)
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError, UnauthorizedError


@pytest.mark.asyncio
async def test_transaction_by_signature_validation_and_errors():
    assert await get_transaction_by_signature(signature=None) == {"error": "Signature is required."}

    class FailClient:
        async def fetch_transaction_by_signature(self, signature: str):
            raise NodeUnreachableError("down")

    assert await get_transaction_by_signature(signature="s", client=FailClient()) == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_transaction_by_reference_validation():
    assert await get_transaction_by_reference(reference=None) == {"error": "Reference is required."}


@pytest.mark.asyncio
async def test_transaction_by_reference_success_and_errors():
    class StubClient:
        async def fetch_transaction_by_reference(self, reference: str):
            return {"reference": reference}

    assert await get_transaction_by_reference(reference="r1", client=StubClient()) == {"reference": "r1"}

    class ApiClient:
        async def fetch_transaction_by_reference(self, reference: str):
            raise NodeUnreachableError("down")

    assert await get_transaction_by_reference(reference="r1", client=ApiClient()) == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_list_transactions_by_block_validation_and_error():
    assert await list_transactions_by_block(signature=None) == {"error": "Signature is required."}

    class FailClient:
        async def fetch_transactions_by_block(self, signature: str, **kwargs):
            raise QortalApiError("fail")

    assert await list_transactions_by_block(signature="s" * 44, client=FailClient()) == {"error": "Qortal API error."}

    class BlockNotFoundClient:
        async def fetch_transactions_by_block(self, signature: str, **kwargs):
            raise QortalApiError("missing", code="BLOCK_UNKNOWN")

    assert await list_transactions_by_block(signature="s" * 44, client=BlockNotFoundClient()) == {"error": "Block not found."}

    class UnexpectedClient:
        async def fetch_transactions_by_block(self, signature: str, **kwargs):
            return {"not": "list"}

    assert await list_transactions_by_block(signature="s" * 44, client=UnexpectedClient()) == {"not": "list"}


@pytest.mark.asyncio
async def test_list_transactions_by_address_validation():
    assert await list_transactions_by_address(address="bad") == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_list_transactions_by_address_unauthorized():
    class UnauthorizedClient:
        async def fetch_transactions_by_address(self, address: str, **kwargs):
            raise UnauthorizedError("nope")

    assert await list_transactions_by_address(address="Q" * 34, client=UnauthorizedClient()) == {
        "error": "Unauthorized or API key required."
    }


@pytest.mark.asyncio
async def test_list_transactions_by_creator_error():
    class FailClient:
        async def fetch_transactions_by_creator(self, public_key: str, **kwargs):
            raise QortalApiError("fail")

    assert await list_transactions_by_creator(
        public_key="A" * 44, confirmation_status="CONFIRMED", client=FailClient()
    ) == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_list_transactions_by_address_success_and_unexpected():
    captured = {}

    class StubClient:
        async def fetch_transactions_by_address(self, address: str, **kwargs):
            captured["address"] = address
            captured.update(kwargs)
            return [{"signature": "s"}]

    result = await list_transactions_by_address(
        address="Q" * 34, limit=5, offset=1, confirmation_status="CONFIRMED", reverse=True, client=StubClient()
    )
    assert captured["limit"] == 5
    assert result == [{"signature": "s"}]

    class UnexpectedClient:
        async def fetch_transactions_by_address(self, *args, **kwargs):
            return "not-a-list"

    assert await list_transactions_by_address(address="Q" * 34, client=UnexpectedClient()) == {"error": "Unexpected response from node."}


@pytest.mark.asyncio
async def test_list_transactions_by_creator_unreachable():
    class FailClient:
        async def fetch_transactions_by_creator(self, *args, **kwargs):
            raise NodeUnreachableError("down")

    assert await list_transactions_by_creator(
        public_key="A" * 44, confirmation_status="CONFIRMED", client=FailClient()
    ) == {"error": "Node unreachable"}
