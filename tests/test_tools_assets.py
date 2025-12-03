import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError, UnauthorizedError
from qortal_mcp.tools.assets import list_assets, get_asset_balances


@pytest.mark.asyncio
async def test_list_assets_clamps_and_errors():
    class StubClient:
        async def fetch_assets(self, **kwargs):
            return [{"assetId": i} for i in range(10)]

    cfg = QortalConfig(max_assets=3, default_assets=2)
    assets = await list_assets(limit=50, client=StubClient(), config=cfg)
    assert len(assets) == 3

    # Unauthorized
    class UnauthorizedClient:
        async def fetch_assets(self, **kwargs):
            raise UnauthorizedError("nope")

    assert await list_assets(client=UnauthorizedClient()) == {"error": "Unauthorized or API key required."}


@pytest.mark.asyncio
async def test_get_asset_balances_validation_and_errors():
    assert await get_asset_balances() == {"error": "At least one address or assetId is required."}
    assert await get_asset_balances(addresses=["bad"]) == {"error": "Invalid Qortal address."}

    class StubClient:
        async def fetch_asset_balances(self, **kwargs):
            return [{"assetId": 1, "assetBalance": "5"}]

    cfg = QortalConfig(max_asset_balances=1, default_asset_balances=1)
    balances = await get_asset_balances(addresses=["Q" * 34], client=StubClient(), config=cfg)
    assert balances == [{"assetId": 1, "assetBalance": "5"}]

    class FailClient:
        async def fetch_asset_balances(self, **kwargs):
            raise NodeUnreachableError("down")

    assert await get_asset_balances(addresses=["Q" * 34], client=FailClient()) == {"error": "Node unreachable"}
