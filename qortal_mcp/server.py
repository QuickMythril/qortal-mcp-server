"""FastAPI application wiring Qortal MCP tools to HTTP routes."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from qortal_mcp.qortal_api import default_client
from qortal_mcp.tools import (
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


@app.get("/tools/node_info")
async def node_info() -> JSONResponse:
    """Proxy for get_node_info tool."""
    result = await get_node_info()
    _log_tool_result("get_node_info", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/account_overview/{address}")
async def account_overview(address: str) -> JSONResponse:
    """Proxy for get_account_overview tool."""
    result = await get_account_overview(address)
    _log_tool_result("get_account_overview", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/balance/{address}")
async def balance(address: str, assetId: int = 0) -> JSONResponse:
    """Proxy for get_balance tool."""
    result = await get_balance(address, asset_id=assetId)
    _log_tool_result("get_balance", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/validate_address/{address}")
async def validate_address_route(address: str) -> JSONResponse:
    """Proxy for validate_address utility."""
    result = validate_address(address)
    _log_tool_result("validate_address", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/name_info/{name}")
async def name_info(name: str) -> JSONResponse:
    """Proxy for get_name_info tool."""
    result = await get_name_info(name)
    _log_tool_result("get_name_info", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/names_by_address/{address}")
async def names_by_address(address: str, limit: int | None = Query(None, ge=0)) -> JSONResponse:
    """Proxy for get_names_by_address tool."""
    result = await get_names_by_address(address, limit=limit)
    _log_tool_result("get_names_by_address", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/trade_offers")
async def trade_offers(limit: int | None = Query(None, ge=0)) -> JSONResponse:
    """Proxy for list_trade_offers tool."""
    result = await list_trade_offers(limit=limit)
    _log_tool_result("list_trade_offers", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/qdn_search")
async def qdn_search(
    address: str | None = None,
    service: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=0),
) -> JSONResponse:
    """Proxy for search_qdn tool."""
    result = await search_qdn(address=address, service=service, limit=limit)
    _log_tool_result("search_qdn", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Ensure HTTP client resources are released on shutdown."""
    await default_client.aclose()


# Run with: uvicorn qortal_mcp.server:app --reload
