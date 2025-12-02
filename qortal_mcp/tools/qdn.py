"""QDN / arbitrary search tools."""

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


def _normalize_search_entry(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "signature": raw.get("signature"),
        "publisher": raw.get("publisher"),
        "service": raw.get("service"),
        "timestamp": raw.get("timestamp"),
    }


def _is_valid_service(service: Optional[int]) -> bool:
    if service is None:
        return False
    try:
        value = int(service)
    except (TypeError, ValueError):
        return False
    return 0 <= value <= 65535


async def search_qdn(
    *,
    address: Optional[str] = None,
    service: Optional[int] = None,
    limit: Optional[int] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """
    Search arbitrary/QDN metadata by publisher address and/or service code.
    """
    if not address and service is None:
        return {"error": "At least one of address or service is required."}

    if address and not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    if service is not None and not _is_valid_service(service):
        return {"error": "Invalid service code."}

    effective_limit = clamp_limit(
        limit, default=config.default_qdn_results, max_value=config.max_qdn_results
    )

    try:
        raw_results = await client.search_qdn(
            address=address,
            service=int(service) if service is not None else None,
            limit=effective_limit,
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
        logger.exception("Unexpected error during QDN search")
        return {"error": "Unexpected error while performing search."}

    results: List[Dict[str, Any]] = []
    if isinstance(raw_results, list):
        for entry in raw_results[:effective_limit]:
            if isinstance(entry, dict):
                results.append(_normalize_search_entry(entry))

    return results[:effective_limit]

