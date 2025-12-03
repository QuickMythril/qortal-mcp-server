"""Additional transaction lookup tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from qortal_mcp.config import default_config
from qortal_mcp.qortal_api import (
    InvalidAddressError,
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import clamp_limit, is_valid_qortal_address
from qortal_mcp.tools.trade import _is_base58

logger = logging.getLogger(__name__)


def _normalize_sig(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    return value.strip()


async def get_transaction_by_signature(signature: str, *, client=default_client) -> Dict[str, Any]:
    normalized = _normalize_sig(signature)
    if not normalized:
        return {"error": "Signature is required."}
    try:
        return await client.fetch_transaction_by_signature(normalized)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching transaction by signature")
        return {"error": "Unexpected error while retrieving transaction."}


async def get_transaction_by_reference(reference: str, *, client=default_client) -> Dict[str, Any]:
    normalized = _normalize_sig(reference)
    if not normalized:
        return {"error": "Reference is required."}
    try:
        return await client.fetch_transaction_by_reference(normalized)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching transaction by reference")
        return {"error": "Unexpected error while retrieving transaction."}


async def list_transactions_by_block(
    signature: str,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config=default_config,
) -> Dict[str, Any]:
    normalized = _normalize_sig(signature)
    if not normalized:
        return {"error": "Signature is required."}
    if not _is_base58(normalized, min_len=43, max_len=200):
        return {"error": "Invalid signature."}
    effective_limit = clamp_limit(limit, default=config.default_tx_search, max_value=100)
    effective_offset = clamp_limit(offset, default=0, max_value=100)
    try:
        txs = await client.fetch_transactions_by_block(
            normalized, limit=effective_limit, offset=effective_offset, reverse=reverse
        )
    except QortalApiError as exc:
        if exc.code in {"BLOCK_UNKNOWN", "INVALID_SIGNATURE"} or exc.status_code == 404:
            return {"error": "Block not found."}
        if exc.code in {"INVALID_PUBLIC_KEY"}:
            return {"error": "Invalid public key."}
        return {"error": "Qortal API error."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except Exception:
        logger.exception("Unexpected error fetching transactions by block")
        return {"error": "Unexpected error while retrieving transactions."}
    return txs


async def list_transactions_by_address(
    address: str,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    confirmation_status: Optional[str] = None,
    reverse: Optional[bool] = None,
    client=default_client,
) -> Dict[str, Any] | list:
    if not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}
    effective_limit = clamp_limit(limit, default=20, max_value=100)
    effective_offset = clamp_limit(offset, default=0, max_value=100)
    normalized_status = None
    if confirmation_status is not None:
        normalized_status = confirmation_status.strip().upper() if isinstance(confirmation_status, str) else None
        if normalized_status not in {None, "CONFIRMED", "UNCONFIRMED", "BOTH"}:
            return {"error": "Invalid confirmation status."}
    try:
        txs = await client.fetch_transactions_by_address(
            address,
            limit=effective_limit,
            offset=effective_offset,
            confirmation_status=normalized_status,
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
        logger.exception("Unexpected error fetching transactions by address")
        return {"error": "Unexpected error while retrieving transactions."}
    return txs if isinstance(txs, list) else {"error": "Unexpected response from node."}


async def list_transactions_by_creator(
    public_key: str,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    confirmation_status: Optional[str] = None,
    reverse: Optional[bool] = None,
    client=default_client,
) -> Dict[str, Any] | list:
    if not public_key or not isinstance(public_key, str) or not _is_base58(public_key, min_len=43, max_len=45):
        return {"error": "Invalid public key."}
    normalized_status = None
    if confirmation_status is not None:
        normalized_status = confirmation_status.strip().upper() if isinstance(confirmation_status, str) else None
        if normalized_status not in {"CONFIRMED", "UNCONFIRMED", "BOTH"}:
            return {"error": "Invalid confirmation status."}
    else:
        return {"error": "confirmationStatus is required."}
    effective_limit = clamp_limit(limit, default=20, max_value=100)
    effective_offset = clamp_limit(offset, default=0, max_value=100)
    try:
        txs = await client.fetch_transactions_by_creator(
            public_key,
            limit=effective_limit,
            offset=effective_offset,
            confirmation_status=normalized_status,
            reverse=reverse,
        )
    except QortalApiError as exc:
        if exc.code in {"INVALID_PUBLIC_KEY"}:
            return {"error": "Invalid public key."}
        return {"error": "Qortal API error."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except Exception:
        logger.exception("Unexpected error fetching transactions by creator")
        return {"error": "Unexpected error while retrieving transactions."}
    return txs if isinstance(txs, list) else {"error": "Unexpected response from node."}
