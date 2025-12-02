import pytest

from qortal_mcp.tools.account import get_account_overview, get_balance, validate_address
from qortal_mcp.qortal_api.client import (
    AddressNotFoundError,
    InvalidAddressError,
    NodeUnreachableError,
    UnauthorizedError,
    QortalApiError,
)


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
async def test_account_overview_happy_path():
    class StubClient:
        async def fetch_address_info(self, address):
            return {
                "address": address,
                "publicKey": "pub",
                "blocksMinted": 10,
                "level": 2,
            }

        async def fetch_address_balance(self, address, asset_id=0):
            return {"balance": "12.345"}

        async def fetch_names_by_owner(self, address):
            return ["name1", "name2", "name3"]

    result = await get_account_overview("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result["balance"] == "12.345"
    assert result["names"] == ["name1", "name2", "name3"]
    assert result["blocksMinted"] == 10
    assert result["level"] == 2


@pytest.mark.asyncio
async def test_account_overview_error_mapping():
    class StubClient:
        async def fetch_address_info(self, *_args, **_kwargs):
            raise AddressNotFoundError("unknown")

    result = await get_account_overview("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Address not found on chain."}


@pytest.mark.asyncio
async def test_get_balance_happy_path():
    class StubClient:
        async def fetch_address_balance(self, *_args, **_kwargs):
            return {"balance": "1.5"}

    result = await get_balance("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", asset_id=0, client=StubClient())
    assert result["balance"] == "1.5"


@pytest.mark.asyncio
async def test_get_balance_error_mapping():
    class StubClient:
        async def fetch_address_balance(self, *_args, **_kwargs):
            raise UnauthorizedError("nope")

    result = await get_balance("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", asset_id=0, client=StubClient())
    assert result == {"error": "Unauthorized or API key required."}


@pytest.mark.asyncio
async def test_get_balance_unreachable_error():
    class StubClient:
        async def fetch_address_balance(self, *_args, **_kwargs):
            raise NodeUnreachableError("down")

    result = await get_balance("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", asset_id=0, client=StubClient())
    assert result == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_get_balance_unexpected_error():
    class StubClient:
        async def fetch_address_balance(self, *_args, **_kwargs):
            raise QortalApiError("boom")

    result = await get_balance("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", asset_id=0, client=StubClient())
    assert result == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_get_balance_invalid_asset_id():
    class DummyClient:
        async def fetch_address_balance(self, *_args, **_kwargs):
            pytest.fail("fetch_address_balance should not be called")

    result = await get_balance("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", asset_id=-1, client=DummyClient())
    assert result == {"error": "Invalid asset id."}
