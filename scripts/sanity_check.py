"""Minimal sanity checks for the Qortal MCP tools."""

from __future__ import annotations

import asyncio
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from qortal_mcp.tools import (  # noqa: E402
    get_account_overview,
    get_balance,
    get_name_info,
    get_names_by_address,
    get_node_info,
    get_node_status,
    list_trade_offers,
    search_qdn,
    validate_address,
)

# Default to a known online minter address (public on chain); override via env.
SAMPLE_ADDRESS = os.getenv("QORTAL_SAMPLE_ADDRESS", "QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV")
# Optional sample name for name lookup; falls back to first owned name if unset.
SAMPLE_NAME = os.getenv("QORTAL_SAMPLE_NAME")
# Opt-in to QDN search in sanity check (can be heavier).
RUN_QDN_SEARCH = os.getenv("RUN_QDN_SANITY", "false").lower() in {"1", "true", "yes"}


async def main() -> None:
    print("Node status:", await get_node_status())
    print("Node info:", await get_node_info())

    print("Validate address:", validate_address(SAMPLE_ADDRESS))

    account_overview = await get_account_overview(SAMPLE_ADDRESS)
    print("Account overview:", account_overview)

    print("Balance:", await get_balance(SAMPLE_ADDRESS))

    names_resp = await get_names_by_address(SAMPLE_ADDRESS, limit=5)
    print("Names by address:", names_resp)

    sample_name = SAMPLE_NAME
    if not sample_name and isinstance(names_resp, dict):
        names_list = names_resp.get("names")
        if isinstance(names_list, list) and names_list:
            sample_name = names_list[0]
    if sample_name:
        print("Name info:", await get_name_info(sample_name))

    print("Trade offers (limit 3):", await list_trade_offers(limit=3))

    if RUN_QDN_SEARCH:
        print("QDN search (service=1, limit=2):", await search_qdn(service=1, limit=2))


if __name__ == "__main__":
    asyncio.run(main())
