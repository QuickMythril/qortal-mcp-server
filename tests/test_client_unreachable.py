import pytest

import httpx

from qortal_mcp.qortal_api.client import (
    NodeUnreachableError,
    QortalApiClient,
)


class FailingAsyncClient:
    def __init__(self, exc: Exception):
        self.exc = exc

    async def get(self, *_args, **_kwargs):
        raise self.exc

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_node_unreachable_maps_error():
    client = QortalApiClient(async_client=FailingAsyncClient(httpx.RequestError("boom")))
    with pytest.raises(NodeUnreachableError):
        await client.fetch_node_status()


@pytest.mark.asyncio
async def test_aclose_closes_owned_client():
    class ClosingClient:
        closed = False

        async def get(self, *_args, **_kwargs):
            return type("Resp", (), {"status_code": 200, "json": lambda self: {}})()

        async def aclose(self):
            ClosingClient.closed = True

    client = QortalApiClient(async_client=None)
    # Force creation
    await client._get_client()
    await client.aclose()
    assert client._client is None
