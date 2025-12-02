"""Name-related tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import (
    AddressNotFoundError,
    InvalidAddressError,
    NameNotFoundError,
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import clamp_limit, is_valid_qortal_address, is_valid_qortal_name

logger = logging.getLogger(__name__)


def _truncate_data(value: Optional[str], max_length: int) -> Optional[str]:
    if value is None:
        return None
    if len(value) <= max_length:
        return value
    return value[: max_length - 15] + "... (truncated)"


def _normalize_name_entry(raw: Any, max_length: int) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    name_value = raw.get("name")
    if not isinstance(name_value, str):
        return None
    registered = (
        raw.get("registered_when")
        or raw.get("registeredWhen")
        or raw.get("registered")
    )
    updated = (
        raw.get("updated_when")
        or raw.get("updatedWhen")
        or raw.get("updated")
    )
    return {
        "name": name_value,
        "owner": raw.get("owner"),
        "data": _truncate_data(raw.get("data"), max_length),
        "registeredWhen": registered,
        "updatedWhen": updated,
        "isForSale": raw.get("is_for_sale") if "is_for_sale" in raw else raw.get("isForSale"),
        "salePrice": raw.get("sale_price") if "sale_price" in raw else raw.get("salePrice"),
    }


async def get_name_info(
    name: str,
    *,
    client=default_client,
    config: QortalConfig = default_config,
) -> Dict[str, Any]:
    """
    Retrieve details about a registered name.
    """
    if not is_valid_qortal_name(name):
        return {"error": "Invalid name."}

    try:
        raw = await client.fetch_name_info(name)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except (AddressNotFoundError, NameNotFoundError):
        return {"error": "Name not found."}
    except InvalidAddressError:
        # Unlikely for names, but treat as invalid.
        return {"error": "Invalid name."}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching name info for %s", name)
        return {"error": "Unexpected error while retrieving name info."}

    return {
        "name": raw.get("name") or name,
        "owner": raw.get("owner"),
        "data": _truncate_data(raw.get("data"), config.max_name_data_preview),
        "isForSale": bool(raw.get("isForSale")),
        "salePrice": raw.get("salePrice"),
    }


async def get_names_by_address(
    address: str,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> Dict[str, Any]:
    """
    List names owned by an address.
    """
    if not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    effective_limit = clamp_limit(limit, default=config.max_names, max_value=config.max_names)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_names)

    try:
        raw_names = await client.fetch_names_by_owner(address, limit=effective_limit, offset=effective_offset, reverse=reverse)
    except InvalidAddressError:
        return {"error": "Invalid Qortal address."}
    except AddressNotFoundError:
        return {"error": "Address not found on chain."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching names for %s", address)
        return {"error": "Unexpected error while retrieving names."}

    names_list: List[str] = []
    source = raw_names
    if isinstance(raw_names, dict) and "names" in raw_names:
        source = raw_names.get("names")
    if isinstance(source, list):
        for item in source[:effective_limit]:
            if isinstance(item, dict):
                value = item.get("name")
                if isinstance(value, str):
                    names_list.append(value)
            elif isinstance(item, str):
                names_list.append(item)

    return {"address": address, "names": names_list[:effective_limit]}


async def get_primary_name(
    address: str,
    *,
    client=default_client,
) -> Dict[str, Any]:
    """Retrieve the primary name for an address."""
    if not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}
    try:
        primary = await client.fetch_primary_name(address)
    except InvalidAddressError:
        return {"error": "Invalid Qortal address."}
    except AddressNotFoundError:
        return {"error": "Address not found on chain."}
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching primary name for %s", address)
        return {"error": "Unexpected error while retrieving primary name."}

    if isinstance(primary, dict) and "name" in primary:
        return {"address": address, "name": primary.get("name")}
    return {"address": address, "name": None}


async def search_names(
    query: str,
    *,
    prefix: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """Search registered names."""
    if not query or not isinstance(query, str):
        return {"error": "Query is required."}
    effective_limit = clamp_limit(limit, default=config.max_names, max_value=config.max_names)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_names)
    try:
        raw = await client.search_names(query, prefix=prefix, limit=effective_limit, offset=effective_offset, reverse=reverse)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error searching names for query %s", query)
        return {"error": "Unexpected error while searching names."}

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[:effective_limit]:
            normalized = _normalize_name_entry(entry, config.max_name_data_preview)
            if normalized:
                results.append(normalized)
    return results[:effective_limit]


async def list_names(
    *,
    after: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """List registered names (alphabetical)."""
    effective_limit = clamp_limit(limit, default=config.max_names, max_value=config.max_names)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_names)
    if after is not None:
        try:
            after = int(after)
        except (TypeError, ValueError):
            return {"error": "Invalid 'after' timestamp."}
    try:
        raw = await client.fetch_all_names(after=after, limit=effective_limit, offset=effective_offset, reverse=reverse)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error listing names")
        return {"error": "Unexpected error while listing names."}

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[:effective_limit]:
            normalized = _normalize_name_entry(entry, config.max_name_data_preview)
            if normalized:
                results.append(normalized)
    return results[:effective_limit]


async def list_names_for_sale(
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """List names currently for sale."""
    effective_limit = clamp_limit(limit, default=config.max_names, max_value=config.max_names)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_names)
    try:
        raw = await client.fetch_names_for_sale(limit=effective_limit, offset=effective_offset, reverse=reverse)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error listing names for sale")
        return {"error": "Unexpected error while listing names for sale."}

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[:effective_limit]:
            normalized = _normalize_name_entry(entry, config.max_name_data_preview)
            if normalized:
                results.append(normalized)
    return results[:effective_limit]
