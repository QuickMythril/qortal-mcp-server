"""Block-related tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError, UnauthorizedError, default_client
from qortal_mcp.tools.validators import clamp_limit

logger = logging.getLogger(__name__)


def _parse_int(value: Any, field: str) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        logger.debug("Invalid %s: %s", field, value)
        return None
    return parsed


async def get_block_at_timestamp(timestamp: Any, *, client=default_client) -> Dict[str, Any]:
    parsed = _parse_int(timestamp, "timestamp")
    if parsed is None or parsed < 0:
        return {"error": "Invalid timestamp."}
    try:
        return await client.fetch_block_at_timestamp(parsed)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching block at timestamp %s", timestamp)
        return {"error": "Unexpected error while retrieving block by timestamp."}


async def get_block_height(*, client=default_client) -> Dict[str, Any]:
    try:
        height = await client.fetch_block_height()
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching block height")
        return {"error": "Unexpected error while retrieving block height."}
    return {"height": height} if isinstance(height, (int, float)) else height


async def get_block_by_height(height: Any, *, client=default_client) -> Dict[str, Any]:
    parsed = _parse_int(height, "height")
    if parsed is None or parsed < 0:
        return {"error": "Invalid height."}
    try:
        return await client.fetch_block_by_height(parsed)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching block by height %s", height)
        return {"error": "Unexpected error while retrieving block by height."}


async def list_block_summaries(
    *,
    start: Any,
    end: Any,
    count: Optional[int] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, Any]:
    start_h = _parse_int(start, "start")
    end_h = _parse_int(end, "end")
    if start_h is None or end_h is None or start_h < 0 or end_h < 0:
        return {"error": "Invalid start or end height."}
    effective_count = None
    if count is not None:
        effective_count = clamp_limit(count, default=config.default_block_summaries, max_value=config.max_block_summaries)
    try:
        summaries = await client.fetch_block_summaries(start=start_h, end=end_h, count=effective_count)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching block summaries")
        return {"error": "Unexpected error while retrieving block summaries."}
    if isinstance(summaries, list):
        return summaries
    return {"error": "Unexpected response from node."}


async def list_block_range(
    *,
    height: Any,
    count: Any,
    reverse: Optional[bool] = None,
    include_online_signatures: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, Any]:
    start_h = _parse_int(height, "height")
    c = _parse_int(count, "count")
    if start_h is None or start_h < 0:
        return {"error": "Invalid height."}
    if c is None or c <= 0:
        return {"error": "Invalid count."}
    effective_count = clamp_limit(c, default=config.default_block_range, max_value=config.max_block_range)
    try:
        blocks = await client.fetch_block_range(
            height=start_h,
            count=effective_count,
            reverse=reverse,
            include_online_signatures=include_online_signatures,
        )
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching block range")
        return {"error": "Unexpected error while retrieving block range."}

    if isinstance(blocks, list):
        return blocks[:effective_count]
    return {"error": "Unexpected response from node."}
