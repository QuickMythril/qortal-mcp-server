import pytest

from qortal_mcp.tools.node import get_node_info
from qortal_mcp.tools.node import get_node_status, _to_int, _to_bool
from qortal_mcp.qortal_api.client import UnauthorizedError, NodeUnreachableError, QortalApiError


@pytest.mark.asyncio
async def test_get_node_info_mapping():
    class StubClient:
        async def fetch_node_info(self):
            return {
                "buildVersion": "qortal-5.0.6-dfa1e57",
                "buildTimestamp": 123,
                "uptime": 456,
                "currentTimestamp": 789,
                "nodeId": "abc",
            }

    result = await get_node_info(client=StubClient())
    assert result["buildVersion"] == "qortal-5.0.6-dfa1e57"
    assert result["currentTime"] == 789


@pytest.mark.asyncio
async def test_get_node_status_mapping():
    class StubClient:
        async def fetch_node_status(self):
            return {
                "height": 123,
                "isSynchronizing": False,
                "syncPercent": 100,
                "isMintingPossible": True,
                "numberOfConnections": 8,
            }

    result = await get_node_status(client=StubClient())
    assert result["height"] == 123
    assert result["numberOfConnections"] == 8


@pytest.mark.asyncio
async def test_get_node_status_error_mapping():
    class StubClient:
        async def fetch_node_status(self):
            raise UnauthorizedError("nope")

    result = await get_node_status(client=StubClient())
    assert result == {"error": "Unauthorized or API key required."}


@pytest.mark.asyncio
async def test_get_node_status_unreachable():
    class StubClient:
        async def fetch_node_status(self):
            raise NodeUnreachableError("down")

    result = await get_node_status(client=StubClient())
    assert result == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_get_node_info_error_mapping():
    class StubClient:
        async def fetch_node_info(self):
            raise UnauthorizedError("nope")

    result = await get_node_info(client=StubClient())
    assert result == {"error": "Unauthorized or API key required."}


@pytest.mark.asyncio
async def test_get_node_info_qortal_api_error():
    class StubClient:
        async def fetch_node_info(self):
            raise QortalApiError("fail")

    result = await get_node_info(client=StubClient())
    assert result == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_get_node_status_qortal_api_error():
    class StubClient:
        async def fetch_node_status(self):
            raise QortalApiError("fail")

    result = await get_node_status(client=StubClient())
    assert result == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_get_node_status_unexpected_exception():
    class StubClient:
        async def fetch_node_status(self):
            raise Exception("boom")

    result = await get_node_status(client=StubClient())
    assert result == {"error": "Unexpected error while retrieving node status."}


@pytest.mark.asyncio
async def test_get_node_info_unexpected_exception():
    class StubClient:
        async def fetch_node_info(self):
            raise Exception("boom")

    result = await get_node_info(client=StubClient())
    assert result == {"error": "Unexpected error while retrieving node info."}


def test_node_helpers():
    assert _to_int("5") == 5
    assert _to_int("bad", default=7) == 7
    assert _to_int(None, allow_none=True) is None
    assert _to_bool("true") is True
    assert _to_bool("FALSE") is False
