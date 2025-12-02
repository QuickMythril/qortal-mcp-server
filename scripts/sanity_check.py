"""Minimal sanity checks for the Qortal MCP tools."""

from __future__ import annotations

import asyncio
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from qortal_mcp.tools import get_account_overview, get_node_status  # noqa: E402

SAMPLE_ADDRESS = os.getenv(
    "QORTAL_SAMPLE_ADDRESS", "QZKfNjpXKd3r5asJ5AZtZRnTj5hZ1a8QwM"
)


async def main() -> None:
    node_status = await get_node_status()
    print("Node status:", node_status)

    account_overview = await get_account_overview(SAMPLE_ADDRESS)
    print("Account overview:", account_overview)


if __name__ == "__main__":
    asyncio.run(main())
