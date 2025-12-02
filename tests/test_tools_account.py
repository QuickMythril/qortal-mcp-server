import pytest

from qortal_mcp.tools.account import get_account_overview, get_balance, validate_address


def test_validate_address_format():
    assert validate_address("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV") == {"isValid": True}
    assert validate_address("bad") == {"isValid": False}


@pytest.mark.asyncio
async def test_account_overview_invalid_address_skips_calls():
    class FailClient:
        async def fetch_address_info(self, *_args, **_kwargs):
            pytest.fail("fetch_address_info should not be called for invalid address")

    result = await get_account_overview("bad", client=FailClient())
    assert result == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_get_balance_invalid_asset_id():
    class DummyClient:
        async def fetch_address_balance(self, *_args, **_kwargs):
            pytest.fail("fetch_address_balance should not be called")

    result = await get_balance("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", asset_id=-1, client=DummyClient())
    assert result == {"error": "Invalid asset id."}
