"""Chat tools (read-only)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import (
    InvalidAddressError,
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import clamp_limit, is_base58_string, is_valid_qortal_address

logger = logging.getLogger(__name__)

MIN_TIMESTAMP_MS = 1_500_000_000_000  # per Core validation


def _truncate(value: Optional[str], *, max_len: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    if len(value) <= max_len:
        return value
    return value[:max_len] + "... (truncated)"


def _normalize_message(raw: Dict[str, Any], *, config: QortalConfig) -> Dict[str, Any]:
    return {
        "timestamp": raw.get("timestamp"),
        "txGroupId": raw.get("txGroupId"),
        "sender": raw.get("sender"),
        "senderName": raw.get("senderName"),
        "recipient": raw.get("recipient"),
        "recipientName": raw.get("recipientName"),
        "chatReference": raw.get("chatReference"),
        "reference": raw.get("reference"),
        "encoding": raw.get("encoding"),
        "data": _truncate(raw.get("data"), max_len=config.max_chat_data_preview),
        "isText": raw.get("isText"),
        "isEncrypted": raw.get("isEncrypted"),
        "signature": raw.get("signature"),
    }


def _normalize_active_chats(raw: Dict[str, Any], *, config: QortalConfig) -> Dict[str, Any]:
    groups_out: List[Dict[str, Any]] = []
    direct_out: List[Dict[str, Any]] = []

    groups = raw.get("groups")
    if isinstance(groups, list):
        for entry in groups:
            if not isinstance(entry, dict):
                continue
            groups_out.append(
                {
                    "groupId": entry.get("groupId"),
                    "groupName": entry.get("groupName"),
                    "timestamp": entry.get("timestamp"),
                    "sender": entry.get("sender"),
                    "senderName": entry.get("senderName"),
                    "signature": entry.get("signature"),
                    "data": _truncate(entry.get("data"), max_len=config.max_chat_data_preview),
                }
            )

    direct = raw.get("direct")
    if isinstance(direct, list):
        for entry in direct:
            if not isinstance(entry, dict):
                continue
            direct_out.append(
                {
                    "address": entry.get("address"),
                    "name": entry.get("name"),
                    "timestamp": entry.get("timestamp"),
                    "sender": entry.get("sender"),
                    "senderName": entry.get("senderName"),
                }
            )

    return {"groups": groups_out, "direct": direct_out}


def _validate_time(value: Optional[int]) -> bool:
    if value is None:
        return True
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return False
    return parsed >= MIN_TIMESTAMP_MS


def _parse_common_filters(
    *,
    tx_group_id: Any,
    involving: Optional[List[str]],
    before: Any,
    after: Any,
    reference: Optional[str],
    chat_reference: Optional[str],
    has_chat_reference: Optional[Any],
    sender: Optional[str],
    encoding: Optional[str],
    limit: Optional[int],
    offset: Optional[int],
    reverse: Optional[bool],
    config: QortalConfig,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, str]]]:
    # Criteria: txGroupId XOR two involving addresses
    has_tx_group = tx_group_id is not None
    involving_list = involving or []
    if has_tx_group and involving_list:
        return None, {"error": "Provide either txGroupId or two involving addresses, not both."}
    if not has_tx_group:
        if len(involving_list) != 2:
            return None, {"error": "Either txGroupId or two involving addresses are required."}
        if any(not is_valid_qortal_address(addr) for addr in involving_list):
            return None, {"error": "Invalid Qortal address in involving filter."}
    else:
        try:
            tx_group_id_int = int(tx_group_id)
        except (TypeError, ValueError):
            return None, {"error": "Invalid group id."}
        if tx_group_id_int < 0:
            return None, {"error": "Invalid group id."}
        tx_group_id = tx_group_id_int

    if before is not None and not _validate_time(before):
        return None, {"error": "Invalid before timestamp."}
    if after is not None and not _validate_time(after):
        return None, {"error": "Invalid after timestamp."}

    if reference is not None and not is_base58_string(reference, min_length=4):
        return None, {"error": "Invalid reference."}
    if chat_reference is not None and not is_base58_string(chat_reference, min_length=4):
        return None, {"error": "Invalid chat reference."}

    if has_chat_reference is not None and not isinstance(has_chat_reference, bool):
        return None, {"error": "hasChatReference must be boolean."}

    if sender and not is_valid_qortal_address(sender):
        return None, {"error": "Invalid Qortal address."}

    normalized_encoding: Optional[str] = None
    if encoding is not None:
        if not isinstance(encoding, str):
            return None, {"error": "Invalid encoding."}
        upper = encoding.strip().upper()
        if upper not in {"BASE58", "BASE64"}:
            return None, {"error": "Invalid encoding."}
        normalized_encoding = upper

    effective_limit = clamp_limit(limit, default=config.default_chat_messages, max_value=config.max_chat_messages)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_chat_messages)

    return (
        {
            "txGroupId": tx_group_id if has_tx_group else None,
            "involving": involving_list if not has_tx_group else None,
            "before": int(before) if before is not None else None,
            "after": int(after) if after is not None else None,
            "reference": reference,
            "chatReference": chat_reference,
            "hasChatReference": has_chat_reference,
            "sender": sender,
            "encoding": normalized_encoding,
            "limit": effective_limit,
            "offset": effective_offset,
            "reverse": reverse,
        },
        None,
    )


def _map_error(exc: Exception) -> Dict[str, str]:
    if isinstance(exc, InvalidAddressError):
        return {"error": "Invalid Qortal address."}
    if isinstance(exc, UnauthorizedError):
        return {"error": "Unauthorized or API key required."}
    if isinstance(exc, NodeUnreachableError):
        return {"error": "Node unreachable"}
    if isinstance(exc, QortalApiError):
        return {"error": "Qortal API error."}
    logger.exception("Unexpected error in chat tool")
    return {"error": "Unexpected error while calling Qortal API."}


async def get_chat_messages(
    *,
    tx_group_id: Any = None,
    involving: Optional[List[str]] = None,
    before: Any = None,
    after: Any = None,
    reference: Optional[str] = None,
    chat_reference: Optional[str] = None,
    has_chat_reference: Optional[Any] = None,
    sender: Optional[str] = None,
    encoding: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    parsed, error = _parse_common_filters(
        tx_group_id=tx_group_id,
        involving=involving,
        before=before,
        after=after,
        reference=reference,
        chat_reference=chat_reference,
        has_chat_reference=has_chat_reference,
        sender=sender,
        encoding=encoding,
        limit=limit,
        offset=offset,
        reverse=reverse,
        config=config,
    )
    if error:
        return error

    try:
        raw = await client.fetch_chat_messages(
            before=parsed["before"],
            after=parsed["after"],
            tx_group_id=parsed["txGroupId"],
            involving=parsed["involving"],
            reference=parsed["reference"],
            chat_reference=parsed["chatReference"],
            has_chat_reference=parsed["hasChatReference"],
            sender=parsed["sender"],
            encoding=parsed["encoding"],
            limit=parsed["limit"],
            offset=parsed["offset"],
            reverse=parsed["reverse"],
        )
    except Exception as exc:  # noqa: BLE001
        return _map_error(exc)

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[: parsed["limit"]]:
            if isinstance(entry, dict):
                results.append(_normalize_message(entry, config=config))
    return results[: parsed["limit"]]


async def count_chat_messages(
    *,
    tx_group_id: Any = None,
    involving: Optional[List[str]] = None,
    before: Any = None,
    after: Any = None,
    reference: Optional[str] = None,
    chat_reference: Optional[str] = None,
    has_chat_reference: Optional[Any] = None,
    sender: Optional[str] = None,
    encoding: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> Dict[str, Any]:
    parsed, error = _parse_common_filters(
        tx_group_id=tx_group_id,
        involving=involving,
        before=before,
        after=after,
        reference=reference,
        chat_reference=chat_reference,
        has_chat_reference=has_chat_reference,
        sender=sender,
        encoding=encoding,
        limit=limit,
        offset=offset,
        reverse=reverse,
        config=config,
    )
    if error:
        return error

    try:
        count = await client.count_chat_messages(
            before=parsed["before"],
            after=parsed["after"],
            tx_group_id=parsed["txGroupId"],
            involving=parsed["involving"],
            reference=parsed["reference"],
            chat_reference=parsed["chatReference"],
            has_chat_reference=parsed["hasChatReference"],
            sender=parsed["sender"],
            encoding=parsed["encoding"],
            limit=parsed["limit"],
            offset=parsed["offset"],
            reverse=parsed["reverse"],
        )
    except Exception as exc:  # noqa: BLE001
        return _map_error(exc)

    return {"count": count}


async def get_chat_message_by_signature(
    *, signature: Optional[str], encoding: Optional[str] = None, client=default_client, config: QortalConfig = default_config
) -> Dict[str, Any]:
    if not signature or not is_base58_string(signature, min_length=10):
        return {"error": "Invalid signature."}

    normalized_encoding: Optional[str] = None
    if encoding is not None:
        if not isinstance(encoding, str):
            return {"error": "Invalid encoding."}
        upper = encoding.strip().upper()
        if upper not in {"BASE58", "BASE64"}:
            return {"error": "Invalid encoding."}
        normalized_encoding = upper

    try:
        raw = await client.fetch_chat_message(signature, encoding=normalized_encoding)
    except Exception as exc:  # noqa: BLE001
        return _map_error(exc)

    if isinstance(raw, dict):
        return _normalize_message(raw, config=config)
    return {"error": "Unexpected response from Qortal API."}


async def get_active_chats(
    *,
    address: Optional[str],
    encoding: Optional[str] = None,
    has_chat_reference: Optional[Any] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> Dict[str, Any]:
    if not address or not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    normalized_encoding: Optional[str] = None
    if encoding is not None:
        if not isinstance(encoding, str):
            return {"error": "Invalid encoding."}
        upper = encoding.strip().upper()
        if upper not in {"BASE58", "BASE64"}:
            return {"error": "Invalid encoding."}
        normalized_encoding = upper

    if has_chat_reference is not None and not isinstance(has_chat_reference, bool):
        return {"error": "hasChatReference must be boolean."}

    try:
        raw = await client.fetch_active_chats(
            address, encoding=normalized_encoding, has_chat_reference=has_chat_reference
        )
    except Exception as exc:  # noqa: BLE001
        return _map_error(exc)

    if isinstance(raw, dict):
        return _normalize_active_chats(raw, config=config)
    return {"error": "Unexpected response from Qortal API."}
