"""FastAPI application wiring Qortal MCP tools to HTTP routes."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from qortal_mcp.qortal_api import default_client
from qortal_mcp.tools import get_account_overview, get_node_status

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Qortal MCP Server",
    description="Read-only Qortal tool surface for LLM agents.",
    version="0.1.0",
)


def _log_tool_result(tool_name: str, result: Dict[str, Any]) -> None:
    if isinstance(result, dict) and result.get("error"):
        logger.warning("%s failed: %s", tool_name, result.get("error"))
    else:
        logger.info("%s succeeded", tool_name)


@app.get("/tools/node_status")
async def node_status() -> JSONResponse:
    """Proxy for get_node_status tool."""
    result = await get_node_status()
    _log_tool_result("get_node_status", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/account_overview/{address}")
async def account_overview(address: str) -> JSONResponse:
    """Proxy for get_account_overview tool."""
    result = await get_account_overview(address)
    _log_tool_result("get_account_overview", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Ensure HTTP client resources are released on shutdown."""
    await default_client.aclose()


# Run with: uvicorn qortal_mcp.server:app --reload

