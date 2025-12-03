import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError, UnauthorizedError
from qortal_mcp.tools.assets import list_assets, get_asset_balances, get_asset_info


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
    assert await get_asset_balances(asset_ids=["bad"]) == {"error": "Invalid asset id."}

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

    class ApiErrorClient:
        async def fetch_asset_balances(self, **kwargs):
            raise QortalApiError("bad", code="INVALID_ASSET_ID")

    assert await get_asset_balances(addresses=["Q" * 34], client=ApiErrorClient()) == {"error": "Asset not found."}


@pytest.mark.asyncio
async def test_get_asset_info_validation_and_mappings():
    assert await get_asset_info() == {"error": "assetId or assetName is required."}
    assert await get_asset_info(asset_id=-1) == {"error": "assetId or assetName is required."}

    class NotFoundClient:
        async def fetch_asset_info(self, **kwargs):
            raise QortalApiError("bad", code="601")

    assert await get_asset_info(asset_id=123, client=NotFoundClient()) == {"error": "Asset not found."}

    class UnauthorizedClient:
        async def fetch_asset_info(self, **kwargs):
            raise UnauthorizedError("nope")

    assert await get_asset_info(asset_name="QORT", client=UnauthorizedClient()) == {"error": "Unauthorized or API key required."}

    class SuccessClient:
        async def fetch_asset_info(self, **kwargs):
            return {"assetId": kwargs.get("asset_id"), "name": "demo"}

    result = await get_asset_info(asset_id=5, client=SuccessClient())
    assert result["assetId"] == 5

    class UnexpectedClient:
        async def fetch_asset_info(self, **kwargs):
            return ["not", "dict"]

    assert await get_asset_info(asset_name="demo", client=UnexpectedClient()) == {"error": "Unexpected response from node."}


@pytest.mark.asyncio
async def test_get_asset_balances_normalizes_ordering_and_truncates():
    captured = {}

    class CaptureClient:
        async def fetch_asset_balances(self, **kwargs):
            captured.update(kwargs)
            return [{"assetId": 1}, {"assetId": 2}, {"assetId": 3}]

    cfg = QortalConfig(default_asset_balances=2, max_asset_balances=2)
    balances = await get_asset_balances(addresses=["Q" * 34], ordering="bad", limit=5, client=CaptureClient(), config=cfg)
    assert captured["ordering"] == "ASSET_BALANCE_ACCOUNT"
    assert len(balances) == 2
