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

    try:
        raw_names = await client.fetch_names_by_owner(address, limit=effective_limit, offset=offset, reverse=reverse)
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
