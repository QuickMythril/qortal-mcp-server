import os

import pytest
import pytest_asyncio
import httpx

from qortal_mcp.qortal_api.client import QortalApiClient
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
SAMPLE_NAME = os.getenv("QORTAL_SAMPLE_NAME", "AGAPE")


pytestmark = pytest.mark.skipif(not LIVE, reason="Live Qortal integration tests are disabled")


@pytest_asyncio.fixture
async def live_client():
    async with httpx.AsyncClient(base_url="http://localhost:12391", timeout=10.0) as httpx_client:
        client = QortalApiClient(async_client=httpx_client)
        yield client


@pytest.mark.asyncio
async def test_live_node_status(live_client):
    status = await get_node_status(client=live_client)
    assert isinstance(status, dict)
    assert "height" in status


@pytest.mark.asyncio
async def test_live_node_info(live_client):
    info = await get_node_info(client=live_client)
    assert isinstance(info, dict)
    if info.get("error") == "Unauthorized or API key required.":
        pytest.skip("Admin info requires API key")
    assert info.get("buildVersion")


@pytest.mark.asyncio
async def test_live_account_overview_and_balance(live_client):
    overview = await get_account_overview(SAMPLE_ADDRESS, client=live_client)
    assert isinstance(overview, dict)
    assert not overview.get("error")
    assert overview.get("address") == SAMPLE_ADDRESS
    balance = await get_balance(SAMPLE_ADDRESS, client=live_client)
    assert balance.get("address") == SAMPLE_ADDRESS
    assert "balance" in balance


@pytest.mark.asyncio
async def test_live_names_lookup(live_client):
    names_resp = await get_names_by_address(SAMPLE_ADDRESS, client=live_client)
    assert isinstance(names_resp, dict)
    if SAMPLE_NAME:
        info = await get_name_info(SAMPLE_NAME, client=live_client)
        assert info.get("name") == SAMPLE_NAME
