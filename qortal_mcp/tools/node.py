"""Node-related tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from qortal_mcp.qortal_api import (
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)

logger = logging.getLogger(__name__)


def _to_int(value: Any, *, default: int = 0, allow_none: bool = False) -> Optional[int]:
    if value is None and allow_none:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


async def get_node_status(client=default_client) -> Dict[str, Any]:
    """
    Summarize node synchronization and connectivity state.

    Args:
        client: Qortal API client (override for testing).

    Returns:
        Dict matching the schema defined in DESIGN.md or an error dict.
    """
    try:
        raw_status = await client.fetch_node_status()
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching node status")
        return {"error": "Unexpected error while retrieving node status."}

    return {
        "height": _to_int(raw_status.get("height") or raw_status.get("chainHeight")),
        "isSynchronizing": _to_bool(
            raw_status.get("isSynchronizing")
            or raw_status.get("isSynchronising")
            or raw_status.get("syncing")
        ),
        "syncPercent": _to_int(raw_status.get("syncPercent"), allow_none=True),
        "isMintingPossible": _to_bool(
            raw_status.get("isMintingPossible") or raw_status.get("mintingPossible")
        ),
        "numberOfConnections": _to_int(
            raw_status.get("numberOfConnections") or raw_status.get("connections")
        ),
    }

