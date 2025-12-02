"""FastAPI application wiring Qortal MCP tools to HTTP routes."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from qortal_mcp import mcp
from qortal_mcp.config import default_config
from qortal_mcp.qortal_api import default_client
from qortal_mcp.rate_limiter import PerKeyRateLimiter
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
logger.setLevel(logging.INFO)
rate_limiter = PerKeyRateLimiter(rate_per_sec=default_config.rate_limit_qps)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    yield
    # Shutdown
    await default_client.aclose()


app = FastAPI(
    title="Qortal MCP Server",
    description="Read-only Qortal tool surface for LLM agents.",
    version="0.1.0",
    lifespan=lifespan,
)


def _log_tool_result(tool_name: str, result: Dict[str, Any]) -> None:
    if isinstance(result, dict) and result.get("error"):
        logger.warning("%s failed: %s", tool_name, result.get("error"))
    else:
        logger.info("%s succeeded", tool_name)


async def _enforce_rate_limit(tool_name: str) -> Optional[JSONResponse]:
    allowed = await rate_limiter.allow(tool_name)
    if not allowed:
        logger.warning("Rate limit exceeded for %s", tool_name)
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})
    return None


@app.get("/tools/node_status")
async def node_status() -> JSONResponse:
    """Proxy for get_node_status tool."""
    limited = await _enforce_rate_limit("get_node_status")
    if limited:
        return limited
    result = await get_node_status()
    _log_tool_result("get_node_status", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/node_info")
async def node_info() -> JSONResponse:
    """Proxy for get_node_info tool."""
    limited = await _enforce_rate_limit("get_node_info")
    if limited:
        return limited
    result = await get_node_info()
    _log_tool_result("get_node_info", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/account_overview/{address}")
async def account_overview(address: str) -> JSONResponse:
    """Proxy for get_account_overview tool."""
    limited = await _enforce_rate_limit("get_account_overview")
    if limited:
        return limited
    result = await get_account_overview(address)
    _log_tool_result("get_account_overview", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/balance/{address}")
async def balance(address: str, assetId: int = 0) -> JSONResponse:
    """Proxy for get_balance tool."""
    limited = await _enforce_rate_limit("get_balance")
    if limited:
        return limited
    result = await get_balance(address, asset_id=assetId)
    _log_tool_result("get_balance", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/validate_address/{address}")
async def validate_address_route(address: str) -> JSONResponse:
    """Proxy for validate_address utility."""
    limited = await _enforce_rate_limit("validate_address")
    if limited:
        return limited
    result = validate_address(address)
    _log_tool_result("validate_address", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/name_info/{name}")
async def name_info(name: str) -> JSONResponse:
    """Proxy for get_name_info tool."""
    limited = await _enforce_rate_limit("get_name_info")
    if limited:
        return limited
    result = await get_name_info(name)
    _log_tool_result("get_name_info", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/names_by_address/{address}")
async def names_by_address(address: str, limit: int | None = Query(None, ge=0)) -> JSONResponse:
    """Proxy for get_names_by_address tool."""
    limited = await _enforce_rate_limit("get_names_by_address")
    if limited:
        return limited
    result = await get_names_by_address(address, limit=limit)
    _log_tool_result("get_names_by_address", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.get("/tools/trade_offers")
async def trade_offers(limit: int | None = Query(None, ge=0)) -> JSONResponse:
    """Proxy for list_trade_offers tool."""
    limited = await _enforce_rate_limit("list_trade_offers")
    if limited:
        return limited
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
    limited = await _enforce_rate_limit("search_qdn")
    if limited:
        return limited
    result = await search_qdn(address=address, service=service, limit=limit)
    _log_tool_result("search_qdn", result if isinstance(result, dict) else {})
    return JSONResponse(content=result)


@app.post("/mcp")
async def mcp_gateway(request: Request) -> JSONResponse:
    """
    Minimal JSON-RPC-like gateway for MCP-style integrations.

    Supported methods:
      - list_tools
      - call_tool (with params: tool, params)
    """
    body = await request.json()
    method = body.get("method")
    rpc_id = body.get("id")
    params = body.get("params") or {}

    if method == "list_tools":
        limited = await _enforce_rate_limit("list_tools")
        if limited:
            return limited
        result = mcp.list_tools()
    elif method == "call_tool":
        tool_name = params.get("tool")
        tool_params = params.get("params") or {}
        limited = await _enforce_rate_limit(tool_name or "call_tool")
        if limited:
            return limited
        result = await mcp.call_tool(tool_name, tool_params)
    else:
        result = {"error": "Unknown method."}

    return JSONResponse(content={"jsonrpc": "2.0", "id": rpc_id, "result": result})


# Run with: uvicorn qortal_mcp.server:app --reload
