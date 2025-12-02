"""
Lightweight JSON-RPC surface for MCP-style tooling.

This keeps a minimal, safe mapping of tool names to existing implementations.
It is intentionally small and stateless; caller must handle authentication to
the HTTP server hosting this adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from qortal_mcp.config import default_config
from qortal_mcp.tools import (
    get_account_overview,
    get_balance,
    get_name_info,
    get_names_by_address,
    get_node_info,
    get_node_status,
    get_node_summary,
    get_node_uptime,
    list_trade_offers,
    search_qdn,
    validate_address,
)
from qortal_mcp.tools.validators import ADDRESS_REGEX, NAME_MAX_LENGTH, NAME_MIN_LENGTH, NAME_REGEX


ADDRESS_PATTERN = ADDRESS_REGEX.pattern
NAME_PATTERN = NAME_REGEX.pattern


def _limit_schema(max_value: int, *, default_minimum: int = 0) -> Dict[str, Any]:
    return {
        "type": "integer",
        "minimum": default_minimum,
        "maximum": max_value,
        "description": f"Optional max items (0-{max_value})",
    }


ToolCallable = Callable[..., Awaitable[Any]] | Callable[..., Any]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    params: Dict[str, Any]
    input_schema: Dict[str, Any]
    callable: ToolCallable


TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    "get_node_status": ToolDefinition(
        name="get_node_status",
        description="Summarize node synchronization and connectivity state.",
        params={},
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        callable=get_node_status,
    ),
    "get_node_info": ToolDefinition(
        name="get_node_info",
        description="Return node version, uptime, and identifiers.",
        params={},
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        callable=get_node_info,
    ),
    "get_node_summary": ToolDefinition(
        name="get_node_summary",
        description="Return node summary information.",
        params={},
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        callable=get_node_summary,
    ),
    "get_node_uptime": ToolDefinition(
        name="get_node_uptime",
        description="Return node uptime info.",
        params={},
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        callable=get_node_uptime,
    ),
    "get_account_overview": ToolDefinition(
        name="get_account_overview",
        description="Return account info, QORT balance, and names for an address.",
        params={"address": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Qortal address (Q-prefixed Base58)",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                }
            },
            "required": ["address"],
            "additionalProperties": False,
        },
        callable=get_account_overview,
    ),
    "get_balance": ToolDefinition(
        name="get_balance",
        description="Return balance for a given address and assetId (default 0/QORT).",
        params={"address": "string (required)", "asset_id": "integer (optional, default 0)"},
        input_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Qortal address (Q-prefixed Base58)",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                },
                "asset_id": {
                    "type": "integer",
                    "description": "Asset id (default 0 for QORT)",
                    "minimum": 0,
                },
            },
            "required": ["address"],
            "additionalProperties": False,
        },
        callable=get_balance,
    ),
    "validate_address": ToolDefinition(
        name="validate_address",
        description="Validate Qortal address format without calling Core.",
        params={"address": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Qortal address (Q-prefixed Base58)",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                }
            },
            "required": ["address"],
            "additionalProperties": False,
        },
        callable=lambda address: validate_address(address),
    ),
    "get_name_info": ToolDefinition(
        name="get_name_info",
        description="Return details about a registered name.",
        params={"name": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Registered Qortal name",
                    "pattern": NAME_PATTERN,
                    "minLength": NAME_MIN_LENGTH,
                    "maxLength": NAME_MAX_LENGTH,
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        callable=get_name_info,
    ),
    "get_names_by_address": ToolDefinition(
        name="get_names_by_address",
        description="List names owned by an address (limit enforced).",
        params={"address": "string (required)", "limit": "integer (optional)", "offset": "integer (optional)", "reverse": "boolean (optional)"},
        input_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Qortal address (Q-prefixed Base58)",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                },
                "limit": _limit_schema(default_config.max_names),
                "offset": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Offset for pagination (optional)",
                },
                "reverse": {
                    "type": "boolean",
                    "description": "Reverse sort order (optional)",
                },
            },
            "required": ["address"],
            "additionalProperties": False,
        },
        callable=get_names_by_address,
    ),
    "list_trade_offers": ToolDefinition(
        name="list_trade_offers",
        description="List open cross-chain trade offers (limit enforced).",
        params={"limit": "integer (optional)"},
        input_schema={
            "type": "object",
            "properties": {
                "limit": _limit_schema(default_config.max_trade_offers),
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_trade_offers,
    ),
    "search_qdn": ToolDefinition(
        name="search_qdn",
        description="Search QDN/arbitrary metadata by address and/or service.",
        params={
            "address": "string (optional)",
            "service": "integer (optional)",
            "limit": "integer (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Publisher address (Q-prefixed Base58)",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                },
                "service": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 65535,
                    "description": "Service code (0-65535)",
                },
                "limit": _limit_schema(default_config.max_qdn_results),
            },
            "required": [],
            "anyOf": [
                {"required": ["address"]},
                {"required": ["service"]},
            ],
            "additionalProperties": False,
        },
        callable=search_qdn,
    ),
}


def list_tools() -> List[Dict[str, Any]]:
    """Return a simple list of available tools."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "params": tool.params,
            "inputSchema": tool.input_schema,
        }
        for tool in TOOL_REGISTRY.values()
    ]


async def call_tool(tool_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Dispatch to a tool by name."""
    params = params or {}
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"error": f"Unknown tool: {tool_name}"}

    # Match parameters by name; tools already handle validation and error shaping.
    try:
        result = tool.callable(**params)
        if isinstance(result, Awaitable):
            return await result  # type: ignore[return-value]
        return result
    except TypeError:
        return {"error": "Invalid parameters."}
    except Exception:
        return {"error": "Unexpected error while calling tool."}
