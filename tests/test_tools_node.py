import pytest

from qortal_mcp.tools.node import get_node_info


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
