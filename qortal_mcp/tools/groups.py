"""Group tools (read-only)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import (
    GroupNotFoundError,
    InvalidAddressError,
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import clamp_limit, is_valid_qortal_address

logger = logging.getLogger(__name__)


def _truncate_text(value: Optional[str], *, max_len: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    if len(value) <= max_len:
        return value
    return value[:max_len] + "... (truncated)"


def _normalize_group(raw: Dict[str, Any], *, config: QortalConfig) -> Dict[str, Any]:
    return {
        "id": raw.get("groupId"),
        "name": raw.get("groupName"),
        "owner": raw.get("owner"),
        "description": _truncate_text(raw.get("description"), max_len=config.max_name_data_preview),
        "created": raw.get("created"),
        "updated": raw.get("updated"),
        "isOpen": raw.get("isOpen"),
        "approvalThreshold": raw.get("approvalThreshold"),
        "minimumBlockDelay": raw.get("minimumBlockDelay"),
        "maximumBlockDelay": raw.get("maximumBlockDelay"),
        "memberCount": raw.get("memberCount"),
        # Present on /groups/member/{address}
        "isAdmin": raw.get("isAdmin"),
    }


def _normalize_member(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "member": raw.get("member"),
        "joined": raw.get("joined"),
        "isAdmin": raw.get("isAdmin"),
    }


def _normalize_invite(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "groupId": raw.get("groupId"),
        "inviter": raw.get("inviter"),
        "invitee": raw.get("invitee"),
        "expiry": raw.get("expiry"),
    }


def _normalize_join_request(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {"groupId": raw.get("groupId"), "joiner": raw.get("joiner")}


def _normalize_ban(raw: Dict[str, Any], *, config: QortalConfig) -> Dict[str, Any]:
    return {
        "groupId": raw.get("groupId"),
        "offender": raw.get("offender"),
        "admin": raw.get("admin"),
        "banned": raw.get("banned"),
        "expiry": raw.get("expiry"),
        "reason": _truncate_text(raw.get("reason"), max_len=config.max_name_data_preview),
    }


def _parse_group_id(group_id: Any) -> Optional[int]:
    try:
        parsed = int(group_id)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _handle_common_errors(exc: Exception) -> Dict[str, str]:
    if isinstance(exc, InvalidAddressError):
        return {"error": "Invalid Qortal address."}
    if isinstance(exc, GroupNotFoundError):
        return {"error": "Group not found."}
    if isinstance(exc, UnauthorizedError):
        return {"error": "Unauthorized or API key required."}
    if isinstance(exc, NodeUnreachableError):
        return {"error": "Node unreachable"}
    if isinstance(exc, QortalApiError):
        return {"error": "Qortal API error."}
    logger.exception("Unexpected group tool error")
    return {"error": "Unexpected error while calling Qortal API."}


async def list_groups(
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    effective_limit = clamp_limit(limit, default=config.default_groups, max_value=config.max_groups)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_groups)

    try:
        raw = await client.fetch_groups(limit=effective_limit, offset=effective_offset, reverse=reverse)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[:effective_limit]:
            if isinstance(entry, dict):
                results.append(_normalize_group(entry, config=config))
    return results[:effective_limit]


async def get_groups_by_owner(
    *,
    address: Optional[str],
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    if not address or not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    try:
        raw = await client.fetch_groups_by_owner(address)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[: config.max_groups]:
            if isinstance(entry, dict):
                results.append(_normalize_group(entry, config=config))
    return results[: config.max_groups]


async def get_groups_by_member(
    *,
    address: Optional[str],
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    if not address or not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    try:
        raw = await client.fetch_groups_by_member(address)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[: config.max_groups]:
            if isinstance(entry, dict):
                results.append(_normalize_group(entry, config=config))
    return results[: config.max_groups]


async def get_group(
    *,
    group_id: Any,
    client=default_client,
    config: QortalConfig = default_config,
) -> Dict[str, Any]:
    parsed_group_id = _parse_group_id(group_id)
    if parsed_group_id is None:
        return {"error": "Invalid group id."}

    try:
        raw = await client.fetch_group(parsed_group_id)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    if isinstance(raw, dict):
        return _normalize_group(raw, config=config)
    return {"error": "Unexpected response from Qortal API."}


async def get_group_members(
    *,
    group_id: Any,
    only_admins: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> Dict[str, Any]:
    parsed_group_id = _parse_group_id(group_id)
    if parsed_group_id is None:
        return {"error": "Invalid group id."}

    if only_admins is not None and not isinstance(only_admins, bool):
        return {"error": "only_admins must be boolean."}

    effective_limit = clamp_limit(limit, default=config.default_group_members, max_value=config.max_group_members)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_group_members)

    try:
        raw = await client.fetch_group_members(
            parsed_group_id,
            only_admins=only_admins,
            limit=effective_limit,
            offset=effective_offset,
            reverse=reverse,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    if not isinstance(raw, dict):
        return {"error": "Unexpected response from Qortal API."}

    members_raw = raw.get("members")
    members: List[Dict[str, Any]] = []
    if isinstance(members_raw, list):
        for entry in members_raw[:effective_limit]:
            if isinstance(entry, dict):
                members.append(_normalize_member(entry))

    return {
        "memberCount": raw.get("memberCount"),
        "adminCount": raw.get("adminCount"),
        "members": members[:effective_limit],
    }


async def get_group_invites_by_address(
    *,
    address: Optional[str],
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    if not address or not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    try:
        raw = await client.fetch_group_invites_by_address(address)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[: config.max_group_events]:
            if isinstance(entry, dict):
                results.append(_normalize_invite(entry))
    return results[: config.max_group_events]


async def get_group_invites_by_group(
    *,
    group_id: Any,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    parsed_group_id = _parse_group_id(group_id)
    if parsed_group_id is None:
        return {"error": "Invalid group id."}

    try:
        raw = await client.fetch_group_invites_by_group(parsed_group_id)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[: config.max_group_events]:
            if isinstance(entry, dict):
                results.append(_normalize_invite(entry))
    return results[: config.max_group_events]


async def get_group_join_requests(
    *,
    group_id: Any,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    parsed_group_id = _parse_group_id(group_id)
    if parsed_group_id is None:
        return {"error": "Invalid group id."}

    try:
        raw = await client.fetch_group_join_requests(parsed_group_id)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[: config.max_group_events]:
            if isinstance(entry, dict):
                results.append(_normalize_join_request(entry))
    return results[: config.max_group_events]


async def get_group_bans(
    *,
    group_id: Any,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    parsed_group_id = _parse_group_id(group_id)
    if parsed_group_id is None:
        return {"error": "Invalid group id."}

    try:
        raw = await client.fetch_group_bans(parsed_group_id)
    except Exception as exc:  # noqa: BLE001
        return _handle_common_errors(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[: config.max_group_events]:
            if isinstance(entry, dict):
                results.append(_normalize_ban(entry, config=config))
    return results[: config.max_group_events]
