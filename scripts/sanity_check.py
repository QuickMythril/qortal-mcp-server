"""Minimal sanity checks for the Qortal MCP tools."""

from __future__ import annotations

import asyncio

from qortal_mcp.tools import get_account_overview, get_node_status

# Sample address for testing. Replace with a known address on your node if needed.
SAMPLE_ADDRESS = "QZKfNjpXKd3r5asJ5AZtZRnTj5hZ1a8QwM"


async def main() -> None:
    node_status = await get_node_status()
    print("Node status:", node_status)

    account_overview = await get_account_overview(SAMPLE_ADDRESS)
    print("Account overview:", account_overview)


if __name__ == "__main__":
    asyncio.run(main())
