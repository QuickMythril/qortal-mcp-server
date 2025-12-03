"""FastAPI application wiring Qortal MCP tools to HTTP routes."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response

from qortal_mcp import mcp
from qortal_mcp.config import default_config
from qortal_mcp.metrics import default_metrics
from qortal_mcp.qortal_api import default_client
from qortal_mcp.rate_limiter import PerKeyRateLimiter
from qortal_mcp.tools import (
    get_account_overview,
    get_balance,
    get_name_info,
    get_names_by_address,
    get_primary_name,
    search_names,
    list_names,
    list_names_for_sale,
    get_node_info,
    get_node_status,
    get_node_summary,
    get_node_uptime,
    list_trade_offers,
    search_qdn,
    validate_address,
    list_groups,
    get_groups_by_owner,
    get_groups_by_member,
    get_group,
    get_group_members,
    get_group_invites_by_address,
    get_group_invites_by_group,
    get_group_join_requests,
    get_group_bans,
    get_chat_messages,
    count_chat_messages,
    get_chat_message_by_signature,
    get_active_chats,
)

logger = logging.getLogger(__name__)
if default_config.log_format.lower() == "json":
    try:
        import json

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "name": record.name,
                }
                for key in ("tool", "request_id", "error"):
                    if hasattr(record, key):
                        payload[key] = getattr(record, key)
                return json.dumps(payload)

        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logging.basicConfig(level=getattr(logging, default_config.log_level.upper(), logging.INFO), handlers=[handler])
    except Exception:
        logging.basicConfig(level=getattr(logging, default_config.log_level.upper(), logging.INFO))
else:
    logging.basicConfig(level=getattr(logging, default_config.log_level.upper(), logging.INFO))
rate_limiter = PerKeyRateLimiter(
    rate_per_sec=default_config.rate_limit_qps,
    per_tool=default_config.per_tool_rate_limits,
)
HEALTH_STATUS = {"status": "ok"}
APP_VERSION = "0.1.0"
MCP_SERVER_NAME = "qortal-mcp-server"
MCP_SERVER_VERSION = APP_VERSION


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    yield
    # Shutdown
    await default_client.aclose()


app = FastAPI(
    title="Qortal MCP Server",
    description="Read-only Qortal tool surface for LLM agents.",
    version=APP_VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    default_metrics.incr_request()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    default_metrics.record_duration(request_id, duration_ms)
    response.headers["X-Request-ID"] = request_id
    return response


def _log_tool_result(tool_name: str, result: Dict[str, Any], request_id: Optional[str] = None) -> None:
    if isinstance(result, dict) and result.get("error"):
        logger.warning(
            "tool=%s outcome=error error=%s request_id=%s",
            tool_name,
            result.get("error"),
            request_id,
            extra={"tool": tool_name, "request_id": request_id, "error": result.get("error")},
        )
        default_metrics.record_tool(tool_name, success=False)
    else:
        logger.info(
            "tool=%s outcome=success request_id=%s",
            tool_name,
            request_id,
            extra={"tool": tool_name, "request_id": request_id},
        )
        default_metrics.record_tool(tool_name, success=True)


async def _enforce_rate_limit(tool_name: str) -> Optional[JSONResponse]:
    allowed = await rate_limiter.allow(tool_name)
    if not allowed:
        logger.warning("tool=%s outcome=rate_limited", tool_name)
        default_metrics.incr_rate_limited()
        # Return a JSON-RPC style error envelope for MCP clients.
        return JSONResponse(
            status_code=429,
            content={"jsonrpc": "2.0", "error": {"code": 429, "message": "Rate limit exceeded"}},
        )
    return None


@app.get("/health")
async def health() -> JSONResponse:
    """Lightweight health endpoint for monitoring."""
    return JSONResponse(content=HEALTH_STATUS)


@app.get("/metrics")
async def metrics() -> JSONResponse:
    """Return in-process metrics snapshot."""
    return JSONResponse(content=default_metrics.snapshot())


@app.get("/tools/node_status")
async def node_status(request: Request) -> JSONResponse:
    """Proxy for get_node_status tool."""
    limited = await _enforce_rate_limit("get_node_status")
    if limited:
        return limited
    result = await get_node_status()
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_node_status", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/node_info")
async def node_info(request: Request) -> JSONResponse:
    """Proxy for get_node_info tool."""
    limited = await _enforce_rate_limit("get_node_info")
    if limited:
        return limited
    result = await get_node_info()
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_node_info", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/node_summary")
async def node_summary(request: Request) -> JSONResponse:
    """Proxy for get_node_summary tool."""
    limited = await _enforce_rate_limit("get_node_summary")
    if limited:
        return limited
    result = await get_node_summary()
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_node_summary", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/node_uptime")
async def node_uptime(request: Request) -> JSONResponse:
    """Proxy for get_node_uptime tool."""
    limited = await _enforce_rate_limit("get_node_uptime")
    if limited:
        return limited
    result = await get_node_uptime()
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_node_uptime", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/account_overview/{address}")
async def account_overview(
    address: str,
    request: Request,
    include_assets: bool | None = Query(False),
    asset_ids: List[int] | None = Query(None),
) -> JSONResponse:
    """Proxy for get_account_overview tool."""
    limited = await _enforce_rate_limit("get_account_overview")
    if limited:
        return limited
    result = await get_account_overview(address, include_assets=include_assets, asset_ids=asset_ids)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_account_overview", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/balance/{address}")
async def balance(address: str, request: Request, assetId: int = 0) -> JSONResponse:
    """Proxy for get_balance tool."""
    limited = await _enforce_rate_limit("get_balance")
    if limited:
        return limited
    result = await get_balance(address, asset_id=assetId)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_balance", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/validate_address/{address}")
async def validate_address_route(address: str, request: Request) -> JSONResponse:
    """Proxy for validate_address utility."""
    limited = await _enforce_rate_limit("validate_address")
    if limited:
        return limited
    result = validate_address(address)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("validate_address", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/name_info/{name}")
async def name_info(name: str, request: Request) -> JSONResponse:
    """Proxy for get_name_info tool."""
    limited = await _enforce_rate_limit("get_name_info")
    if limited:
        return limited
    result = await get_name_info(name)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_name_info", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/names_by_address/{address}")
async def names_by_address(
    address: str,
    request: Request,
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for get_names_by_address tool."""
    limited = await _enforce_rate_limit("get_names_by_address")
    if limited:
        return limited
    result = await get_names_by_address(address, limit=limit, offset=offset, reverse=reverse)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_names_by_address", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/primary_name/{address}")
async def primary_name(address: str, request: Request) -> JSONResponse:
    """Proxy for get_primary_name tool."""
    limited = await _enforce_rate_limit("get_primary_name")
    if limited:
        return limited
    result = await get_primary_name(address)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_primary_name", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/search_names")
async def search_names_route(
    request: Request,
    query: str | None = None,
    prefix: bool | None = Query(None),
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for search_names tool."""
    limited = await _enforce_rate_limit("search_names")
    if limited:
        return limited
    result = await search_names(query or "", prefix=prefix, limit=limit, offset=offset, reverse=reverse)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("search_names", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/list_names")
async def list_names_route(
    request: Request,
    after: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for list_names tool."""
    limited = await _enforce_rate_limit("list_names")
    if limited:
        return limited
    result = await list_names(after=after, limit=limit, offset=offset, reverse=reverse)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("list_names", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/list_names_for_sale")
async def list_names_for_sale_route(
    request: Request,
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for list_names_for_sale tool."""
    limited = await _enforce_rate_limit("list_names_for_sale")
    if limited:
        return limited
    result = await list_names_for_sale(limit=limit, offset=offset, reverse=reverse)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("list_names_for_sale", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/trade_offers")
async def trade_offers(request: Request, limit: int | None = Query(None, ge=0)) -> JSONResponse:
    """Proxy for list_trade_offers tool."""
    limited = await _enforce_rate_limit("list_trade_offers")
    if limited:
        return limited
    result = await list_trade_offers(limit=limit)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("list_trade_offers", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/hidden_trade_offers")
async def hidden_trade_offers(request: Request, limit: int | None = Query(None, ge=0)) -> JSONResponse:
    """Proxy for list_hidden_trade_offers tool."""
    limited = await _enforce_rate_limit("list_hidden_trade_offers")
    if limited:
        return limited
    result = await list_hidden_trade_offers(limit=limit)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("list_hidden_trade_offers", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/groups")
async def groups_route(
    request: Request,
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for list_groups tool."""
    limited = await _enforce_rate_limit("list_groups")
    if limited:
        return limited
    result = await list_groups(limit=limit, offset=offset, reverse=reverse)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("list_groups", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/groups/owner/{address}")
async def groups_by_owner(address: str, request: Request) -> JSONResponse:
    """Proxy for get_groups_by_owner tool."""
    limited = await _enforce_rate_limit("get_groups_by_owner")
    if limited:
        return limited
    result = await get_groups_by_owner(address=address)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_groups_by_owner", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/groups/member/{address}")
async def groups_by_member(address: str, request: Request) -> JSONResponse:
    """Proxy for get_groups_by_member tool."""
    limited = await _enforce_rate_limit("get_groups_by_member")
    if limited:
        return limited
    result = await get_groups_by_member(address=address)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_groups_by_member", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/group/{group_id}")
async def group_detail(group_id: int, request: Request) -> JSONResponse:
    """Proxy for get_group tool."""
    limited = await _enforce_rate_limit("get_group")
    if limited:
        return limited
    result = await get_group(group_id=group_id)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_group", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/group/{group_id}/members")
async def group_members(
    group_id: int,
    request: Request,
    onlyAdmins: bool | None = Query(None),
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for get_group_members tool."""
    limited = await _enforce_rate_limit("get_group_members")
    if limited:
        return limited
    result = await get_group_members(
        group_id=group_id, only_admins=onlyAdmins, limit=limit, offset=offset, reverse=reverse
    )
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_group_members", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/group_invites/address/{address}")
async def group_invites_by_address(address: str, request: Request) -> JSONResponse:
    """Proxy for get_group_invites_by_address tool."""
    limited = await _enforce_rate_limit("get_group_invites_by_address")
    if limited:
        return limited
    result = await get_group_invites_by_address(address=address)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_group_invites_by_address", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/group/{group_id}/invites")
async def group_invites_by_group(group_id: int, request: Request) -> JSONResponse:
    """Proxy for get_group_invites_by_group tool."""
    limited = await _enforce_rate_limit("get_group_invites_by_group")
    if limited:
        return limited
    result = await get_group_invites_by_group(group_id=group_id)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_group_invites_by_group", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/group/{group_id}/join_requests")
async def group_join_requests(group_id: int, request: Request) -> JSONResponse:
    """Proxy for get_group_join_requests tool."""
    limited = await _enforce_rate_limit("get_group_join_requests")
    if limited:
        return limited
    result = await get_group_join_requests(group_id=group_id)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_group_join_requests", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/group/{group_id}/bans")
async def group_bans(group_id: int, request: Request) -> JSONResponse:
    """Proxy for get_group_bans tool."""
    limited = await _enforce_rate_limit("get_group_bans")
    if limited:
        return limited
    result = await get_group_bans(group_id=group_id)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_group_bans", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/chat/messages")
async def chat_messages(
    request: Request,
    txGroupId: int | None = Query(None),
    involving: List[str] | None = Query(None),
    before: int | None = Query(None),
    after: int | None = Query(None),
    reference: str | None = Query(None),
    chatreference: str | None = Query(None),
    haschatreference: bool | None = Query(None),
    sender: str | None = Query(None),
    encoding: str | None = Query(None),
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
    decode_text: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for get_chat_messages tool."""
    limited = await _enforce_rate_limit("get_chat_messages")
    if limited:
        return limited
    result = await get_chat_messages(
        tx_group_id=txGroupId,
        involving=involving,
        before=before,
        after=after,
        reference=reference,
        chat_reference=chatreference,
        has_chat_reference=haschatreference,
        sender=sender,
        encoding=encoding,
        limit=limit,
        offset=offset,
        reverse=reverse,
        decode_text=decode_text,
    )
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_chat_messages", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/chat/messages/count")
async def chat_messages_count(
    request: Request,
    txGroupId: int | None = Query(None),
    involving: List[str] | None = Query(None),
    before: int | None = Query(None),
    after: int | None = Query(None),
    reference: str | None = Query(None),
    chatreference: str | None = Query(None),
    haschatreference: bool | None = Query(None),
    sender: str | None = Query(None),
    encoding: str | None = Query(None),
    limit: int | None = Query(None, ge=0),
    offset: int | None = Query(None, ge=0),
    reverse: bool | None = Query(None),
    decode_text: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for count_chat_messages tool."""
    limited = await _enforce_rate_limit("count_chat_messages")
    if limited:
        return limited
    result = await count_chat_messages(
        tx_group_id=txGroupId,
        involving=involving,
        before=before,
        after=after,
        reference=reference,
        chat_reference=chatreference,
        has_chat_reference=haschatreference,
        sender=sender,
        encoding=encoding,
        limit=limit,
        offset=offset,
        reverse=reverse,
        decode_text=decode_text,
    )
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("count_chat_messages", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/chat/message/{signature}")
async def chat_message_by_signature(
    signature: str, request: Request, encoding: str | None = Query(None), decode_text: bool | None = Query(None)
) -> JSONResponse:
    """Proxy for get_chat_message_by_signature tool."""
    limited = await _enforce_rate_limit("get_chat_message_by_signature")
    if limited:
        return limited
    result = await get_chat_message_by_signature(signature=signature, encoding=encoding, decode_text=decode_text)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_chat_message_by_signature", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/chat/active/{address}")
async def active_chats(
    address: str,
    request: Request,
    encoding: str | None = Query(None),
    haschatreference: bool | None = Query(None),
    decode_text: bool | None = Query(None),
) -> JSONResponse:
    """Proxy for get_active_chats tool."""
    limited = await _enforce_rate_limit("get_active_chats")
    if limited:
        return limited
    result = await get_active_chats(
        address=address,
        encoding=encoding,
        has_chat_reference=haschatreference,
        decode_text=decode_text,
    )
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("get_active_chats", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.get("/tools/qdn_search")
async def qdn_search(
    request: Request,
    address: str | None = None,
    service: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=0),
) -> JSONResponse:
    """Proxy for search_qdn tool."""
    limited = await _enforce_rate_limit("search_qdn")
    if limited:
        return limited
    result = await search_qdn(address=address, service=service, limit=limit)
    request_id = getattr(request.state, "request_id", None)
    _log_tool_result("search_qdn", result if isinstance(result, dict) else {}, request_id)
    return JSONResponse(content=result)


@app.post("/mcp")
async def mcp_gateway(request: Request) -> JSONResponse:
    """
    Minimal JSON-RPC-like gateway for MCP-style integrations.

    Supported methods:
      - initialize
      - list_tools / tools/list
      - call_tool / tools/call
    """
    request_id = getattr(request.state, "request_id", None)
    start_time = time.time()

    def _respond(payload: Dict[str, Any], status_code: int = 200, *, outcome: str, method_label: Optional[str] = None, tool_label: Optional[str] = None, error_code: Optional[int] = None) -> JSONResponse:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            "mcp outcome=%s method=%s tool=%s id=%s status=%s duration_ms=%.2f error_code=%s",
            outcome,
            method_label,
            tool_label,
            payload.get("id"),
            status_code,
            duration_ms,
            error_code,
            extra={"request_id": request_id, "tool": tool_label, "error": error_code},
        )
        return JSONResponse(status_code=status_code, content=payload)

    try:
        body = await request.json()
    except Exception:
        payload = _jsonrpc_error_payload(None, -32700, "Parse error", request_id=request_id)
        return _respond(payload, status_code=400, outcome="error", method_label=None, error_code=-32700)

    if not isinstance(body, dict):
        payload = _jsonrpc_error_payload(None, -32600, "Invalid request", request_id=request_id)
        return _respond(payload, status_code=400, outcome="error", method_label=None, error_code=-32600)

    method = body.get("method")
    rpc_id = body.get("id")
    raw_params = body.get("params")
    if raw_params is None:
        params = {}
    elif isinstance(raw_params, dict):
        params = raw_params
    else:
        payload = _jsonrpc_error_payload(rpc_id, -32602, "Invalid params", request_id=request_id)
        return _respond(payload, outcome="error", method_label=method, error_code=-32602)

    if not method:
        payload = _jsonrpc_error_payload(rpc_id, -32600, "Invalid request", request_id=request_id)
        return _respond(payload, outcome="error", method_label=None, error_code=-32600)

    if method == "initialize":
        protocol_version = params.get("protocolVersion")
        if not isinstance(protocol_version, str) or not protocol_version:
            payload = _jsonrpc_error_payload(rpc_id, -32602, "Invalid params", request_id=request_id)
            return _respond(payload, outcome="error", method_label=method, error_code=-32602)

        logger.debug(
            "mcp initialize requested protocol=%s request_id=%s",
            protocol_version,
            request_id,
            extra={"request_id": request_id},
        )
        result = {
            "protocolVersion": protocol_version,
            "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
            "capabilities": {"tools": {"listChanged": False}},
        }
        return _respond(
            _jsonrpc_success_payload(rpc_id, result, request_id=request_id),
            outcome="success",
            method_label=method,
        )

    if method in ("list_tools", "tools/list"):
        limited = await _enforce_rate_limit("list_tools")
        if limited:
            return limited
        result = {"tools": mcp.list_tools()}
        return _respond(
            _jsonrpc_success_payload(rpc_id, result, request_id=request_id),
            outcome="success",
            method_label=method,
        )

    if method in ("call_tool", "tools/call"):
        tool_name = params.get("tool") or params.get("name")
        tool_params = params.get("params")
        if tool_params is None:
            tool_params = params.get("arguments") or {}
        if not isinstance(tool_name, str) or not tool_name.strip():
            payload = _jsonrpc_error_payload(rpc_id, -32602, "Invalid params", request_id=request_id)
            return _respond(
                payload,
                outcome="error",
                method_label=method,
                tool_label=None,
                error_code=-32602,
            )
        if not isinstance(tool_params, dict):
            payload = _jsonrpc_error_payload(rpc_id, -32602, "Invalid params", request_id=request_id)
            return _respond(payload, outcome="error", method_label=method, tool_label=tool_name, error_code=-32602)
        limited = await _enforce_rate_limit(tool_name or "call_tool")
        if limited:
            return limited
        result = await mcp.call_tool(tool_name, tool_params)
        wrapped = _wrap_tool_result(result)
        return _respond(
            _jsonrpc_success_payload(rpc_id, wrapped, request_id=request_id),
            outcome="success",
            method_label=method,
            tool_label=tool_name,
        )

    if method in ("notifications/initialized", "initialized"):
        # Notifications should not return a JSON-RPC response body.
        logger.debug(
            "mcp initialized notification received request_id=%s",
            request_id,
            extra={"request_id": request_id},
        )
        return Response(status_code=204)

    payload = _jsonrpc_error_payload(rpc_id, -32601, "Method not found", request_id=request_id)
    return _respond(payload, outcome="error", method_label=method, error_code=-32601)


# Run with: uvicorn qortal_mcp.server:app --reload


def _jsonrpc_success_payload(rpc_id: Any, result: Any, request_id: Optional[str] = None) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _jsonrpc_error_payload(rpc_id: Any, code: int, message: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


def _wrap_tool_result(result: Any) -> Dict[str, Any]:
    """
    Shape tool outputs into MCP-friendly content array.
    """
    # Tool-level errors are returned in-band with isError flag.
    if isinstance(result, dict) and "error" in result:
        message = result.get("error") or "Error"
        wrapped = {"content": [{"type": "text", "text": str(message)}], "isError": True}
        # Preserve structured error details for capable clients.
        wrapped["structuredContent"] = result
        return wrapped

    # Plain string results are returned directly as text.
    if isinstance(result, str):
        return {"content": [{"type": "text", "text": result}]}

    # For structured or primitive outputs, provide a text rendering plus structuredContent.
    try:
        text_repr = json.dumps(result, ensure_ascii=True)
    except Exception:
        text_repr = str(result)
    wrapped_result: Dict[str, Any] = {
        "content": [{"type": "text", "text": text_repr}],
        "structuredContent": result,
    }
    return wrapped_result
