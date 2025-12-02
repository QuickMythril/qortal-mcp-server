"""Asset-related tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import NodeUnreachableError, QortalApiError, UnauthorizedError, default_client
from qortal_mcp.tools.validators import clamp_limit, is_valid_qortal_address

logger = logging.getLogger(__name__)


def _parse_asset_id(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


async def list_assets(
    *,
    include_data: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """
    List known assets (optionally including data field).
    """
    effective_limit = clamp_limit(limit, default=config.default_assets, max_value=config.max_assets)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_assets)

    try:
        raw_assets = await client.fetch_assets(
            include_data=include_data,
            limit=effective_limit,
            offset=effective_offset,
            reverse=reverse,
        )
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error listing assets")
        return {"error": "Unexpected error while listing assets."}

    if isinstance(raw_assets, list):
        return raw_assets[:effective_limit]
    return {"error": "Unexpected response from node."}


async def get_asset_info(
    *,
    asset_id: Optional[int] = None,
    asset_name: Optional[str] = None,
    client=default_client,
) -> Dict[str, Any]:
    """
    Fetch asset info by id or name.
    """
    parsed_asset_id = _parse_asset_id(asset_id)
    name_value = asset_name.strip() if isinstance(asset_name, str) else None

    if parsed_asset_id is None and not name_value:
        return {"error": "assetId or assetName is required."}

    try:
        raw = await client.fetch_asset_info(asset_id=parsed_asset_id, asset_name=name_value)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError as exc:
        if exc.code in {"INVALID_ASSET_ID"}:
            return {"error": "Invalid asset id."}
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching asset info")
        return {"error": "Unexpected error while retrieving asset info."}

    if isinstance(raw, dict):
        return raw
    return {"error": "Unexpected response from node."}


async def get_asset_balances(
    *,
    addresses: Optional[List[str]] = None,
    asset_ids: Optional[List[int]] = None,
    ordering: Optional[str] = None,
    exclude_zero: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """
    Fetch asset balances for addresses and/or asset ids.
    """
    address_list = addresses or []
    asset_id_list = asset_ids or []

    if not address_list and not asset_id_list:
        return {"error": "At least one address or assetId is required."}

    for addr in address_list:
        if not is_valid_qortal_address(addr):
            return {"error": "Invalid Qortal address."}

    parsed_asset_ids: List[int] = []
    for raw_id in asset_id_list:
        parsed = _parse_asset_id(raw_id)
        if parsed is None:
            return {"error": "Invalid asset id."}
        parsed_asset_ids.append(parsed)

    allowed_orderings = {"ASSET_BALANCE_ACCOUNT", "ACCOUNT_ASSET", "ASSET_ACCOUNT"}
    normalized_ordering = ordering.strip().upper() if isinstance(ordering, str) else "ASSET_BALANCE_ACCOUNT"
    if normalized_ordering not in allowed_orderings:
        normalized_ordering = "ASSET_BALANCE_ACCOUNT"

    effective_limit = clamp_limit(limit, default=config.default_asset_balances, max_value=config.max_asset_balances)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_asset_balances)

    try:
        raw_balances = await client.fetch_asset_balances(
            addresses=address_list or None,
            asset_ids=parsed_asset_ids or None,
            ordering=normalized_ordering,
            exclude_zero=exclude_zero,
            limit=effective_limit,
            offset=effective_offset,
            reverse=reverse,
        )
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError as exc:
        if exc.code in {"INVALID_ASSET_ID"}:
            return {"error": "Invalid asset id."}
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching asset balances")
        return {"error": "Unexpected error while retrieving asset balances."}

    if isinstance(raw_balances, list):
        return raw_balances[:effective_limit]
    return {"error": "Unexpected response from node."}
