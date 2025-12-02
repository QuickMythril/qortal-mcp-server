"""Additional block lookup tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError, UnauthorizedError, default_client
from qortal_mcp.tools.validators import clamp_limit

logger = logging.getLogger(__name__)


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_sig(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    return value.strip()


async def get_block_by_signature(signature: str, *, client=default_client) -> Dict[str, Any]:
    normalized = _normalize_sig(signature)
    if not normalized:
        return {"error": "Signature is required."}
    if not _is_base58(normalized, min_len=43, max_len=200):
        return {"error": "Invalid signature."}
    try:
        return await client.fetch_block_by_signature(normalized)
    except QortalApiError as exc:
        if exc.code in {"BLOCK_UNKNOWN", "INVALID_SIGNATURE"} or exc.status_code == 404:
            return {"error": "Block not found."}
        return {"error": "Qortal API error."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except Exception:
        logger.exception("Unexpected error fetching block by signature")
        return {"error": "Unexpected error while retrieving block."}


async def get_block_height_by_signature(signature: str, *, client=default_client) -> Dict[str, Any]:
    normalized = _normalize_sig(signature)
    if not normalized:
        return {"error": "Signature is required."}
    if not _is_base58(normalized, min_len=43, max_len=200):
        return {"error": "Invalid signature."}
    try:
        height = await client.fetch_block_height_by_signature(normalized)
    except QortalApiError as exc:
        if exc.code in {"BLOCK_UNKNOWN", "INVALID_SIGNATURE"} or exc.status_code == 404:
            return {"error": "Block not found."}
        return {"error": "Qortal API error."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except Exception:
        logger.exception("Unexpected error fetching block height by signature")
        return {"error": "Unexpected error while retrieving block height."}
    return {"height": height} if isinstance(height, (int, float)) else height


async def get_first_block(*, client=default_client) -> Any:
    try:
        return await client.fetch_first_block()
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching first block")
        return {"error": "Unexpected error while retrieving first block."}


async def get_last_block(*, client=default_client) -> Any:
    try:
        return await client.fetch_last_block()
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching last block")
        return {"error": "Unexpected error while retrieving last block."}


async def get_minting_info_by_height(height: Any, *, client=default_client) -> Dict[str, Any]:
    parsed = _parse_int(height)
    if parsed is None or parsed < 0:
        return {"error": "Invalid height."}
    try:
        return await client.fetch_minting_info_by_height(parsed)
    except QortalApiError as exc:
        if exc.code in {"BLOCK_UNKNOWN"} or exc.status_code == 404:
            return {"error": "Block not found."}
        if exc.code in {"INVALID_DATA"}:
            return {"error": "Minting info unavailable for this block."}
        return {"error": "Qortal API error."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except Exception:
        logger.exception("Unexpected error fetching minting info")
        return {"error": "Unexpected error while retrieving minting info."}


async def list_block_signers(
    *,
    address: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config=None,
) -> List[Any] | Dict[str, Any]:
    effective_limit = clamp_limit(limit, default=50, max_value=500)
    effective_offset = clamp_limit(offset, default=0, max_value=500)
    params: Dict[str, Any] = {}
    if address:
        params["address"] = address
    params["limit"] = effective_limit
    params["offset"] = effective_offset
    if reverse is not None:
        params["reverse"] = reverse
    try:
        # fetch_block_signers currently ignores params; include them when wiring if client adds support
        signers = await client.fetch_block_signers()
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError as exc:
        if exc.code in {"BLOCK_UNKNOWN"}:
            return {"error": "Block not found."}
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching block signers")
        return {"error": "Unexpected error while retrieving block signers."}
    if isinstance(signers, list):
        return signers
    return {"error": "Unexpected response from node."}
