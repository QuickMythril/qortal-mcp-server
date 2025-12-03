"""Transaction search tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import (
    InvalidAddressError,
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import clamp_limit, is_valid_qortal_address

logger = logging.getLogger(__name__)


def _normalize_confirmation_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"CONFIRMED", "UNCONFIRMED", "BOTH"}:
            return normalized
    return None


def _parse_int(value: Any, field: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.debug("Invalid %s: %s", field, value)
        return None


def _normalize_tx_types(tx_types: Optional[List[Any]]) -> Optional[List[Any]]:
    if tx_types is None:
        return None
    if not isinstance(tx_types, list):
        return None
    normalized: List[Any] = []
    for entry in tx_types:
        if isinstance(entry, str):
            normalized.append(entry.strip().upper())
        else:
            normalized.append(entry)
    return normalized


async def search_transactions(
    *,
    start_block: Optional[Any] = None,
    block_limit: Optional[Any] = None,
    tx_types: Optional[List[Any]] = None,
    address: Optional[str] = None,
    confirmation_status: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """
    Search transactions (read-only) with Core constraints.
    """
    normalized_status = _normalize_confirmation_status(confirmation_status)
    if confirmation_status is not None and normalized_status is None:
        return {"error": "Invalid confirmation status."}

    start_b = _parse_int(start_block, "startBlock") if start_block is not None else None
    block_lim = _parse_int(block_limit, "blockLimit") if block_limit is not None else None

    if (start_b is not None or block_lim is not None) and normalized_status != "CONFIRMED":
        return {"error": "Block range requires confirmationStatus=CONFIRMED."}

    normalized_tx_types = _normalize_tx_types(tx_types)

    if address and not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    requested_limit: Optional[int] = None
    if limit is not None:
        try:
            requested_limit = int(limit)
        except (TypeError, ValueError):
            requested_limit = None

    effective_limit = clamp_limit(limit, default=config.default_tx_search, max_value=config.max_tx_search)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_tx_search)

    if not normalized_tx_types and not address and requested_limit is not None and requested_limit > config.max_tx_search:
        # Core requires txType/address or limit<=20; enforce based on caller's requested limit before clamping.
        return {"error": "txType or address is required when limit exceeds 20."}

    try:
        raw = await client.search_transactions(
            start_block=start_b,
            block_limit=block_lim,
            tx_types=normalized_tx_types,
            address=address,
            confirmation_status=normalized_status,
            limit=effective_limit,
            offset=effective_offset,
            reverse=reverse,
        )
    except InvalidAddressError:
        return {"error": "Invalid Qortal address."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error during transaction search")
        return {"error": "Unexpected error while searching transactions."}

    if isinstance(raw, list):
        return raw[:effective_limit]
    return {"error": "Unexpected response from node."}
