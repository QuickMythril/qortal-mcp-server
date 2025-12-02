import os

import pytest

from qortal_mcp.tools import (
    get_account_overview,
    get_balance,
    get_name_info,
    get_names_by_address,
    get_node_info,
    get_node_status,
)


LIVE = os.getenv("LIVE_QORTAL") in {"1", "true", "yes"}
SAMPLE_ADDRESS = os.getenv("QORTAL_SAMPLE_ADDRESS", "QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV")
SAMPLE_NAME = os.getenv("QORTAL_SAMPLE_NAME")


pytestmark = pytest.mark.skipif(not LIVE, reason="Live Qortal integration tests are disabled")


@pytest.mark.asyncio
async def test_live_node_status():
    status = await get_node_status()
    assert isinstance(status, dict)
    assert "height" in status


@pytest.mark.asyncio
async def test_live_node_info():
    info = await get_node_info()
    assert isinstance(info, dict)
    assert info.get("buildVersion")


@pytest.mark.asyncio
async def test_live_account_overview_and_balance():
    overview = await get_account_overview(SAMPLE_ADDRESS)
    assert isinstance(overview, dict)
    assert overview.get("address") == SAMPLE_ADDRESS
    balance = await get_balance(SAMPLE_ADDRESS)
    assert balance.get("address") == SAMPLE_ADDRESS
    assert "balance" in balance


@pytest.mark.asyncio
async def test_live_names_lookup():
    names_resp = await get_names_by_address(SAMPLE_ADDRESS)
    assert isinstance(names_resp, dict)
    if SAMPLE_NAME:
        info = await get_name_info(SAMPLE_NAME)
        assert info.get("name") == SAMPLE_NAME
