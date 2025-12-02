import pytest

from qortal_mcp.qortal_api.client import (
    NodeUnreachableError,
    QortalApiClient,
    httpx,
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
