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
    get_primary_name,
    search_names,
    list_names,
    list_names_for_sale,
    get_node_info,
    get_node_status,
    get_node_summary,
    get_node_uptime,
    list_trade_offers,
    list_hidden_trade_offers,
    get_trade_detail,
    list_completed_trades,
    get_trade_ledger,
    get_trade_price,
    search_qdn,
    list_assets,
    get_asset_info,
    get_asset_balances,
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
    get_block_at_timestamp,
    get_block_height,
    get_block_by_height,
    list_block_summaries,
    list_block_range,
    search_transactions,
    get_block_by_signature,
    get_block_height_by_signature,
    get_first_block,
    get_last_block,
    get_transaction_by_signature,
    get_transaction_by_reference,
    list_transactions_by_block,
    list_transactions_by_address,
    list_transactions_by_creator,
    validate_address,
)
from qortal_mcp.tools.validators import ADDRESS_REGEX, NAME_MAX_LENGTH, NAME_MIN_LENGTH


ADDRESS_PATTERN = ADDRESS_REGEX.pattern
NAME_PATTERN = r".+"
BASE58_PATTERN = r"^[1-9A-HJ-NP-Za-km-z]+$"


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
    "get_primary_name": ToolDefinition(
        name="get_primary_name",
        description="Return the primary name for an address.",
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
                },
            },
            "required": ["address"],
            "additionalProperties": False,
        },
        callable=get_primary_name,
    ),
    "search_names": ToolDefinition(
        name="search_names",
        description="Search registered names (query, optional prefix).",
        params={
            "query": "string (required)",
            "prefix": "boolean (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "prefix": {"type": "boolean", "description": "Prefix-only search"},
                "limit": _limit_schema(default_config.max_names),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        callable=search_names,
    ),
    "list_names": ToolDefinition(
        name="list_names",
        description="List registered names (alphabetical).",
        params={
            "after": "integer (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "after": {"type": "integer", "description": "Only names registered/updated after this timestamp"},
                "limit": _limit_schema(default_config.max_names),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_names,
    ),
    "list_names_for_sale": ToolDefinition(
        name="list_names_for_sale",
        description="List names currently for sale.",
        params={
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "limit": _limit_schema(default_config.max_names),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_names_for_sale,
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
        params={
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
            "foreign_blockchain": "string (optional, e.g., BITCOIN/LITECOIN)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "limit": _limit_schema(default_config.max_trade_offers),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
                "foreign_blockchain": {
                    "type": "string",
                    "description": "Optional foreign blockchain filter (e.g., BITCOIN, LITECOIN)",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_trade_offers,
    ),
    "list_hidden_trade_offers": ToolDefinition(
        name="list_hidden_trade_offers",
        description="List hidden cross-chain trade offers.",
        params={
            "foreign_blockchain": "string (optional, e.g., BITCOIN/LITECOIN)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "foreign_blockchain": {
                    "type": "string",
                    "description": "Optional foreign blockchain filter (e.g., BITCOIN, LITECOIN)",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_hidden_trade_offers,
    ),
    "get_trade_detail": ToolDefinition(
        name="get_trade_detail",
        description="Get detailed trade info for a specific AT address.",
        params={"at_address": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {
                "at_address": {
                    "type": "string",
                    "description": "AT address of the trade",
                },
            },
            "required": ["at_address"],
            "additionalProperties": False,
        },
        callable=get_trade_detail,
    ),
    "list_completed_trades": ToolDefinition(
        name="list_completed_trades",
        description="List completed cross-chain trades.",
        params={
            "foreign_blockchain": "string (optional)",
            "minimum_timestamp": "integer (optional, ms since epoch)",
            "buyer_public_key": "string (optional)",
            "seller_public_key": "string (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "foreign_blockchain": {"type": "string"},
                "minimum_timestamp": {"type": "integer", "minimum": 1},
                "buyer_public_key": {"type": "string"},
                "seller_public_key": {"type": "string"},
                "limit": _limit_schema(default_config.max_trade_offers),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_completed_trades,
    ),
    "get_trade_ledger": ToolDefinition(
        name="get_trade_ledger",
        description="Fetch trade ledger entries for a public key.",
        params={
            "public_key": "string (required, Base58)",
            "minimum_timestamp": "integer (optional, ms since epoch)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "public_key": {"type": "string"},
                "minimum_timestamp": {"type": "integer", "minimum": 1},
            },
            "required": ["public_key"],
            "additionalProperties": False,
        },
        callable=get_trade_ledger,
    ),
    "get_trade_price": ToolDefinition(
        name="get_trade_price",
        description="Fetch estimated trading price for a blockchain.",
        params={
            "blockchain": "string (required, e.g., BITCOIN)",
            "max_trades": "integer (optional)",
            "inverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "blockchain": {"type": "string"},
                "max_trades": {"type": "integer", "minimum": 1},
                "inverse": {"type": "boolean"},
            },
            "required": ["blockchain"],
            "additionalProperties": False,
        },
        callable=get_trade_price,
    ),
    "list_groups": ToolDefinition(
        name="list_groups",
        description="List groups with member counts (limit enforced).",
        params={"limit": "integer (optional)", "offset": "integer (optional)", "reverse": "boolean (optional)"},
        input_schema={
            "type": "object",
            "properties": {
                "limit": _limit_schema(default_config.max_groups),
                "offset": {"type": "integer", "minimum": 0, "maximum": default_config.max_groups},
                "reverse": {"type": "boolean"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_groups,
    ),
    "get_groups_by_owner": ToolDefinition(
        name="get_groups_by_owner",
        description="List groups owned by an address.",
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
        callable=get_groups_by_owner,
    ),
    "get_groups_by_member": ToolDefinition(
        name="get_groups_by_member",
        description="List groups where an address is a member.",
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
        callable=get_groups_by_member,
    ),
    "get_group": ToolDefinition(
        name="get_group",
        description="Fetch a single group by id.",
        params={"group_id": "integer (required)"},
        input_schema={
            "type": "object",
            "properties": {"group_id": {"type": "integer", "minimum": 1}},
            "required": ["group_id"],
            "additionalProperties": False,
        },
        callable=get_group,
    ),
    "get_group_members": ToolDefinition(
        name="get_group_members",
        description="List members for a group (optionally admins only).",
        params={
            "group_id": "integer (required)",
            "only_admins": "boolean (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "group_id": {"type": "integer", "minimum": 1},
                "only_admins": {"type": "boolean"},
                "limit": _limit_schema(default_config.max_group_members),
                "offset": {"type": "integer", "minimum": 0, "maximum": default_config.max_group_members},
                "reverse": {"type": "boolean"},
            },
            "required": ["group_id"],
            "additionalProperties": False,
        },
        callable=get_group_members,
    ),
    "get_group_invites_by_address": ToolDefinition(
        name="get_group_invites_by_address",
        description="List pending group invites for an address (trimmed).",
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
        callable=get_group_invites_by_address,
    ),
    "get_group_invites_by_group": ToolDefinition(
        name="get_group_invites_by_group",
        description="List pending invites for a group (trimmed).",
        params={"group_id": "integer (required)"},
        input_schema={
            "type": "object",
            "properties": {"group_id": {"type": "integer", "minimum": 1}},
            "required": ["group_id"],
            "additionalProperties": False,
        },
        callable=get_group_invites_by_group,
    ),
    "get_group_join_requests": ToolDefinition(
        name="get_group_join_requests",
        description="List join requests for a group (trimmed).",
        params={"group_id": "integer (required)"},
        input_schema={
            "type": "object",
            "properties": {"group_id": {"type": "integer", "minimum": 1}},
            "required": ["group_id"],
            "additionalProperties": False,
        },
        callable=get_group_join_requests,
    ),
    "get_group_bans": ToolDefinition(
        name="get_group_bans",
        description="List bans for a group (trimmed).",
        params={"group_id": "integer (required)"},
        input_schema={
            "type": "object",
            "properties": {"group_id": {"type": "integer", "minimum": 1}},
            "required": ["group_id"],
            "additionalProperties": False,
        },
        callable=get_group_bans,
    ),
    "get_chat_messages": ToolDefinition(
        name="get_chat_messages",
        description="Retrieve chat messages with filters.",
        params={
            "tx_group_id": "integer (optional)",
            "involving": "array of 2 addresses (required if tx_group_id missing)",
            "before": "integer timestamp ms (optional, >=1500000000000)",
            "after": "integer timestamp ms (optional, >=1500000000000)",
            "reference": "Base58 string (optional)",
            "chat_reference": "Base58 string (optional)",
            "has_chat_reference": "boolean (optional)",
            "sender": "address (optional)",
            "encoding": "BASE58 or BASE64 (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "tx_group_id": {"type": "integer", "minimum": 0},
                "involving": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": ADDRESS_PATTERN,
                        "minLength": 34,
                        "maxLength": 34,
                    },
                    "minItems": 2,
                    "maxItems": 2,
                },
                "before": {"type": "integer", "minimum": 1500000000000},
                "after": {"type": "integer", "minimum": 1500000000000},
                "reference": {"type": "string", "pattern": BASE58_PATTERN},
                "chat_reference": {"type": "string", "pattern": BASE58_PATTERN},
                "has_chat_reference": {"type": "boolean"},
                "sender": {
                    "type": "string",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                },
                "encoding": {"type": "string", "enum": ["BASE58", "BASE64"]},
                "limit": _limit_schema(default_config.max_chat_messages),
            "offset": {"type": "integer", "minimum": 0, "maximum": default_config.max_chat_messages},
            "reverse": {"type": "boolean"},
            "decode_text": {"type": "boolean", "description": "Decode plaintext data to UTF-8 when possible"},
        },
        "required": [],
        "additionalProperties": False,
    },
    callable=get_chat_messages,
    ),
    "count_chat_messages": ToolDefinition(
        name="count_chat_messages",
        description="Count chat messages matching filters.",
        params={
            "tx_group_id": "integer (optional)",
            "involving": "array of 2 addresses (required if tx_group_id missing)",
            "before": "integer timestamp ms (optional, >=1500000000000)",
            "after": "integer timestamp ms (optional, >=1500000000000)",
            "reference": "Base58 string (optional)",
            "chat_reference": "Base58 string (optional)",
            "has_chat_reference": "boolean (optional)",
            "sender": "address (optional)",
            "encoding": "BASE58 or BASE64 (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "tx_group_id": {"type": "integer", "minimum": 0},
                "involving": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": ADDRESS_PATTERN,
                        "minLength": 34,
                        "maxLength": 34,
                    },
                    "minItems": 2,
                    "maxItems": 2,
                },
                "before": {"type": "integer", "minimum": 1500000000000},
                "after": {"type": "integer", "minimum": 1500000000000},
                "reference": {"type": "string", "pattern": BASE58_PATTERN},
                "chat_reference": {"type": "string", "pattern": BASE58_PATTERN},
                "has_chat_reference": {"type": "boolean"},
                "sender": {
                    "type": "string",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                },
                "encoding": {"type": "string", "enum": ["BASE58", "BASE64"]},
                "limit": _limit_schema(default_config.max_chat_messages),
                "offset": {"type": "integer", "minimum": 0, "maximum": default_config.max_chat_messages},
                "reverse": {"type": "boolean"},
                "decode_text": {"type": "boolean", "description": "Decode plaintext data to UTF-8 when possible"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=count_chat_messages,
    ),
    "get_chat_message_by_signature": ToolDefinition(
        name="get_chat_message_by_signature",
        description="Fetch a single chat message by signature.",
        params={"signature": "Base58 string (required)", "encoding": "BASE58 or BASE64 (optional)"},
        input_schema={
            "type": "object",
            "properties": {
                "signature": {"type": "string", "pattern": BASE58_PATTERN, "minLength": 10},
                "encoding": {"type": "string", "enum": ["BASE58", "BASE64"]},
                "decode_text": {"type": "boolean", "description": "Decode plaintext data to UTF-8 when possible"},
            },
            "required": ["signature"],
            "additionalProperties": False,
        },
        callable=get_chat_message_by_signature,
    ),
    "get_active_chats": ToolDefinition(
        name="get_active_chats",
        description="Summarize recent group/direct chats for an address.",
        params={
            "address": "string (required)",
            "encoding": "BASE58 or BASE64 (optional)",
            "has_chat_reference": "boolean (optional)",
        },
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
                "encoding": {"type": "string", "enum": ["BASE58", "BASE64"]},
                "has_chat_reference": {"type": "boolean"},
                "decode_text": {"type": "boolean", "description": "Decode plaintext data to UTF-8 when possible"},
            },
            "required": ["address"],
            "additionalProperties": False,
        },
        callable=get_active_chats,
    ),
    "get_block_at_timestamp": ToolDefinition(
        name="get_block_at_timestamp",
        description="Fetch block at/just before a timestamp.",
        params={"timestamp": "integer (required, ms since epoch)"},
        input_schema={
            "type": "object",
            "properties": {"timestamp": {"type": "integer", "minimum": 0}},
            "required": ["timestamp"],
            "additionalProperties": False,
        },
        callable=get_block_at_timestamp,
    ),
    "get_block_height": ToolDefinition(
        name="get_block_height",
        description="Fetch current blockchain height.",
        params={},
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        callable=get_block_height,
    ),
    "get_block_by_height": ToolDefinition(
        name="get_block_by_height",
        description="Fetch block info by height.",
        params={"height": "integer (required)"},
        input_schema={
            "type": "object",
            "properties": {"height": {"type": "integer", "minimum": 0}},
            "required": ["height"],
            "additionalProperties": False,
        },
        callable=get_block_by_height,
    ),
    "list_block_summaries": ToolDefinition(
        name="list_block_summaries",
        description="List block summaries over a height range.",
        params={
            "start": "integer (required)",
            "end": "integer (required)",
            "count": "integer (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "integer", "minimum": 0},
                "end": {"type": "integer", "minimum": 0},
                "count": _limit_schema(default_config.max_block_summaries),
            },
            "required": ["start", "end"],
            "additionalProperties": False,
        },
        callable=list_block_summaries,
    ),
    "list_block_range": ToolDefinition(
        name="list_block_range",
        description="List blocks starting from height with count and options.",
        params={
            "height": "integer (required)",
            "count": "integer (required)",
            "reverse": "boolean (optional)",
            "include_online_signatures": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "height": {"type": "integer", "minimum": 0},
                "count": _limit_schema(default_config.max_block_range, default_minimum=1),
                "reverse": {"type": "boolean"},
                "include_online_signatures": {"type": "boolean"},
            },
            "required": ["height", "count"],
            "additionalProperties": False,
        },
        callable=list_block_range,
    ),
    "search_transactions": ToolDefinition(
        name="search_transactions",
        description="Search transactions by type/address with Core constraints.",
        params={
            "start_block": "integer (optional)",
            "block_limit": "integer (optional)",
            "tx_types": "array of transaction types (optional)",
            "address": "string (optional)",
            "confirmation_status": "string (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "start_block": {"type": "integer", "minimum": 0},
                "block_limit": {"type": "integer", "minimum": 0},
                "tx_types": {"type": "array"},
                "address": {
                    "type": "string",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                },
                "confirmation_status": {
                    "type": "string",
                    "enum": ["CONFIRMED", "UNCONFIRMED", "BOTH"],
                },
                "limit": _limit_schema(default_config.max_tx_search),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=search_transactions,
    ),
    "get_block_by_signature": ToolDefinition(
        name="get_block_by_signature",
        description="Fetch block by signature.",
        params={"signature": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {"signature": {"type": "string"}},
            "required": ["signature"],
            "additionalProperties": False,
        },
        callable=get_block_by_signature,
    ),
    "get_block_height_by_signature": ToolDefinition(
        name="get_block_height_by_signature",
        description="Fetch block height by signature.",
        params={"signature": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {"signature": {"type": "string"}},
            "required": ["signature"],
            "additionalProperties": False,
        },
        callable=get_block_height_by_signature,
    ),
    "get_first_block": ToolDefinition(
        name="get_first_block",
        description="Fetch first block.",
        params={},
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        callable=get_first_block,
    ),
    "get_last_block": ToolDefinition(
        name="get_last_block",
        description="Fetch last block.",
        params={},
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        callable=get_last_block,
    ),
    "get_transaction_by_signature": ToolDefinition(
        name="get_transaction_by_signature",
        description="Fetch transaction by signature.",
        params={"signature": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {"signature": {"type": "string"}},
            "required": ["signature"],
            "additionalProperties": False,
        },
        callable=get_transaction_by_signature,
    ),
    "get_transaction_by_reference": ToolDefinition(
        name="get_transaction_by_reference",
        description="Fetch transaction by reference.",
        params={"reference": "string (required)"},
        input_schema={
            "type": "object",
            "properties": {"reference": {"type": "string"}},
            "required": ["reference"],
            "additionalProperties": False,
        },
        callable=get_transaction_by_reference,
    ),
    "list_transactions_by_block": ToolDefinition(
        name="list_transactions_by_block",
        description="List transactions in a block by signature.",
        params={
            "signature": "string (required)",
            "limit": "integer (optional, max 100)",
            "offset": "integer (optional, max 100)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "signature": {"type": "string"},
                "limit": {"type": "integer", "minimum": 0, "maximum": 100},
                "offset": {"type": "integer", "minimum": 0, "maximum": 100},
                "reverse": {"type": "boolean"},
            },
            "required": ["signature"],
            "additionalProperties": False,
        },
        callable=list_transactions_by_block,
    ),
    "list_transactions_by_address": ToolDefinition(
        name="list_transactions_by_address",
        description="List transactions involving an address.",
        params={
            "address": "string (required)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "confirmation_status": "string (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "pattern": ADDRESS_PATTERN,
                    "minLength": 34,
                    "maxLength": 34,
                },
                "limit": {"type": "integer", "minimum": 0, "maximum": 100},
                "offset": {"type": "integer", "minimum": 0},
                "confirmation_status": {
                    "type": "string",
                    "enum": ["CONFIRMED", "UNCONFIRMED", "BOTH"],
                },
                "reverse": {"type": "boolean"},
            },
            "required": ["address"],
            "additionalProperties": False,
        },
        callable=list_transactions_by_address,
    ),
    "list_transactions_by_creator": ToolDefinition(
        name="list_transactions_by_creator",
        description="List transactions by creator public key.",
        params={
            "public_key": "string (required, Base58)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "confirmation_status": "string (required)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "public_key": {"type": "string"},
                "limit": {"type": "integer", "minimum": 0, "maximum": 100},
                "offset": {"type": "integer", "minimum": 0},
                "confirmation_status": {
                    "type": "string",
                    "enum": ["CONFIRMED", "UNCONFIRMED", "BOTH"],
                },
                "reverse": {"type": "boolean"},
            },
            "required": ["public_key", "confirmation_status"],
            "additionalProperties": False,
        },
        callable=list_transactions_by_creator,
    ),
    "search_qdn": ToolDefinition(
        name="search_qdn",
        description="Search QDN/arbitrary metadata by address and/or service.",
        params={
            "address": "string (optional)",
            "service": "string or integer (optional)",
            "limit": "integer (optional)",
            "confirmation_status": "string (optional, CONFIRMED/UNCONFIRMED/BOTH)",
            "start_block": "integer (optional, >=0)",
            "block_limit": "integer (optional, >=0)",
            "tx_group_id": "integer (optional, >=0)",
            "name": "string (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
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
                    "oneOf": [
                        {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 65535,
                            "description": "Service code (numeric)",
                        },
                        {
                            "type": "string",
                            "description": "Service name (enum)",
                            "enum": [
                                "AUTO_UPDATE",
                                "ARBITRARY_DATA",
                                "QCHAT_ATTACHMENT",
                                "QCHAT_ATTACHMENT_PRIVATE",
                                "ATTACHMENT",
                                "ATTACHMENT_PRIVATE",
                                "FILE",
                                "FILE_PRIVATE",
                                "FILES",
                                "CHAIN_DATA",
                                "WEBSITE",
                                "GIT_REPOSITORY",
                                "IMAGE",
                                "IMAGE_PRIVATE",
                                "THUMBNAIL",
                                "QCHAT_IMAGE",
                                "VIDEO",
                                "VIDEO_PRIVATE",
                                "AUDIO",
                                "AUDIO_PRIVATE",
                                "QCHAT_AUDIO",
                                "QCHAT_VOICE",
                                "VOICE",
                                "VOICE_PRIVATE",
                                "PODCAST",
                                "BLOG",
                                "BLOG_POST",
                                "BLOG_COMMENT",
                                "DOCUMENT",
                                "DOCUMENT_PRIVATE",
                                "LIST",
                                "PLAYLIST",
                                "APP",
                                "METADATA",
                                "JSON",
                                "GIF_REPOSITORY",
                                "STORE",
                                "PRODUCT",
                                "OFFER",
                                "COUPON",
                                "CODE",
                                "PLUGIN",
                                "EXTENSION",
                                "GAME",
                                "ITEM",
                                "NFT",
                                "DATABASE",
                                "SNAPSHOT",
                                "COMMENT",
                                "CHAIN_COMMENT",
                                "MAIL",
                                "MAIL_PRIVATE",
                                "MESSAGE",
                                "MESSAGE_PRIVATE",
                            ],
                        },
                    ],
                },
                "limit": _limit_schema(default_config.max_qdn_results),
                "confirmation_status": {
                    "type": "string",
                    "description": "Confirmation status (CONFIRMED, UNCONFIRMED, BOTH)",
                    "enum": ["CONFIRMED", "UNCONFIRMED", "BOTH"],
                },
                "start_block": {"type": "integer", "minimum": 0},
                "block_limit": {"type": "integer", "minimum": 0},
                "tx_group_id": {"type": "integer", "minimum": 0},
                "name": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
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
    "list_assets": ToolDefinition(
        name="list_assets",
        description="List registered assets.",
        params={
            "include_data": "boolean (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "include_data": {"type": "boolean", "description": "Include asset data field"},
                "limit": _limit_schema(default_config.max_assets),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=list_assets,
    ),
    "get_asset_info": ToolDefinition(
        name="get_asset_info",
        description="Return asset info by id or name.",
        params={
            "asset_id": "integer (optional)",
            "asset_name": "string (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "asset_id": {"type": "integer", "minimum": 0},
                "asset_name": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=get_asset_info,
    ),
    "get_asset_balances": ToolDefinition(
        name="get_asset_balances",
        description="Fetch asset balances filtered by addresses and/or asset IDs.",
        params={
            "addresses": "array of Qortal addresses (optional)",
            "asset_ids": "array of asset IDs (optional)",
            "ordering": "string (optional ordering)",
            "exclude_zero": "boolean (optional)",
            "limit": "integer (optional)",
            "offset": "integer (optional)",
            "reverse": "boolean (optional)",
        },
        input_schema={
            "type": "object",
            "properties": {
                "addresses": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": ADDRESS_PATTERN,
                        "minLength": 34,
                        "maxLength": 34,
                    },
                },
                "asset_ids": {"type": "array", "items": {"type": "integer", "minimum": 0}},
                "ordering": {
                    "type": "string",
                    "description": "Ordering (ASSET_BALANCE_ACCOUNT, ACCOUNT_ASSET, ASSET_ACCOUNT)",
                },
                "exclude_zero": {"type": "boolean"},
                "limit": _limit_schema(default_config.max_asset_balances),
                "offset": {"type": "integer", "minimum": 0},
                "reverse": {"type": "boolean"},
            },
            "required": [],
            "additionalProperties": False,
        },
        callable=get_asset_balances,
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
