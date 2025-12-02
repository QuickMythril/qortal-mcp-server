import pytest

from qortal_mcp.tools.account import get_account_overview, get_balance, validate_address, _normalize_balance, _extract_names
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
async def test_account_overview_unreachable():
    class StubClient:
        async def fetch_address_info(self, *_args, **_kwargs):
            raise NodeUnreachableError("down")

    result = await get_account_overview("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Node unreachable"}


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


def test_normalize_balance_variants():
    assert _normalize_balance({"balance": "1.2"}) == "1.2"
    assert _normalize_balance({"available": 5}) == "5"
    assert _normalize_balance(3.14) == "3.14"
    assert _normalize_balance(None) == "0"


def test_extract_names_variants():
    assert _extract_names({"names": [{"name": "a"}, {"name": "b"}]}, 5) == ["a", "b"]
    assert _extract_names(["x", {"name": "y"}], 2) == ["x", "y"]
    assert _extract_names("not-list", 2) == []


@pytest.mark.asyncio
async def test_account_overview_names_error_unreachable():
    class StubClient:
        async def fetch_address_info(self, address):
            return {"address": address}

        async def fetch_address_balance(self, address, asset_id=0):
            return {"balance": "1"}

        async def fetch_names_by_owner(self, address):
            raise NodeUnreachableError("down")

    result = await get_account_overview("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_account_overview_names_optional_on_api_error():
    class StubClient:
        async def fetch_address_info(self, address):
            return {"address": address}

        async def fetch_address_balance(self, address, asset_id=0):
            return {"balance": "1"}

        async def fetch_names_by_owner(self, address):
            raise QortalApiError("oops")

    result = await get_account_overview("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result["names"] == []


@pytest.mark.asyncio
async def test_account_overview_balance_unexpected_error():
    class StubClient:
        async def fetch_address_info(self, address):
            return {"address": address}

        async def fetch_address_balance(self, address, asset_id=0):
            raise Exception("boom")

    result = await get_account_overview("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Unexpected error while retrieving account balance."}
