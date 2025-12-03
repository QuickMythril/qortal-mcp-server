import pytest

from qortal_mcp.tools.blocks_extra import (
    get_block_by_signature,
    get_block_height_by_signature,
    get_first_block,
    get_last_block,
)
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError


@pytest.mark.asyncio
async def test_block_by_signature_validation_and_errors():
    assert await get_block_by_signature(signature=None) == {"error": "Signature is required."}

    class FailClient:
        async def fetch_block_by_signature(self, signature: str):
            raise NodeUnreachableError("down")

    # Signature too short triggers validation error, so use a realistic length
    result = await get_block_by_signature(signature="s" * 44, client=FailClient())
    # Tool maps unexpected exceptions to generic API error
    assert result in ({"error": "Node unreachable"}, {"error": "Qortal API error."})


@pytest.mark.asyncio
async def test_block_height_by_signature_validation():
    assert await get_block_height_by_signature(signature=None) == {"error": "Signature is required."}

    class StubClient:
        async def fetch_block_height_by_signature(self, signature: str):
            return 5

    result = await get_block_height_by_signature(signature="s" * 44, client=StubClient())
    assert result in ({"height": 5}, 5)


@pytest.mark.asyncio
async def test_block_height_by_signature_error_mapping():
    class FailClient:
        async def fetch_block_height_by_signature(self, signature: str):
            raise NodeUnreachableError("down")

    assert await get_block_height_by_signature(signature="s" * 44, client=FailClient()) == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_first_last_block_error():
    class FailClient:
        async def fetch_first_block(self):
            raise QortalApiError("fail")

    assert await get_first_block(client=FailClient()) == {"error": "Qortal API error."}

    class FailClient2:
        async def fetch_last_block(self):
            raise NodeUnreachableError("down")

    assert await get_last_block(client=FailClient2()) == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_block_by_signature_success():
    class StubClient:
        async def fetch_block_by_signature(self, signature: str):
            return {"signature": signature, "height": 5}

    result = await get_block_by_signature(signature="s" * 44, client=StubClient())
    assert result["height"] == 5
