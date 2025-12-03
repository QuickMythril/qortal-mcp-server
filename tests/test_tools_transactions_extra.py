import pytest

from qortal_mcp.tools.transactions_extra import (
    get_transaction_by_signature,
    get_transaction_by_reference,
    list_transactions_by_block,
    list_transactions_by_address,
    list_transactions_by_creator,
)
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError


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
async def test_list_transactions_by_block_validation_and_error():
    assert await list_transactions_by_block(signature=None) == {"error": "Signature is required."}

    class FailClient:
        async def fetch_transactions_by_block(self, signature: str, **kwargs):
            raise QortalApiError("fail")

    assert await list_transactions_by_block(signature="s" * 44, client=FailClient()) == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_list_transactions_by_address_validation():
    assert await list_transactions_by_address(address="bad") == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_list_transactions_by_creator_error():
    class FailClient:
        async def fetch_transactions_by_creator(self, public_key: str, **kwargs):
            raise QortalApiError("fail")

    assert await list_transactions_by_creator(
        public_key="A" * 44, confirmation_status="CONFIRMED", client=FailClient()
    ) == {"error": "Qortal API error."}
