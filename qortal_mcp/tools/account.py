"""Account-related tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import (
    AddressNotFoundError,
    InvalidAddressError,
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import is_valid_qortal_address

logger = logging.getLogger(__name__)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_balance(balance_payload: Any) -> str:
    """
    Normalize the balance field as a string. The Core API typically returns
    a decimal string, but we coerce any numeric type to string for safety.
    """
    balance_value: Any = None
    if isinstance(balance_payload, (str, int, float)):
        return str(balance_payload)
    if isinstance(balance_payload, dict):
        if "balance" in balance_payload:
            balance_value = balance_payload.get("balance")
        elif "available" in balance_payload:
            balance_value = balance_payload.get("available")
    if balance_value is None:
        return "0"
    return str(balance_value)


def _extract_names(raw_names: Any, max_items: int) -> List[str]:
    names: List[str] = []
    source = raw_names
    if isinstance(raw_names, dict) and "names" in raw_names:
        source = raw_names.get("names")

    if isinstance(source, list):
        for item in source[:max_items]:
            if isinstance(item, dict):
                name_value = item.get("name")
                if isinstance(name_value, str):
                    names.append(name_value)
            elif isinstance(item, str):
                names.append(item)
    return names[:max_items]


async def get_account_overview(
    address: str,
    *,
    client=default_client,
    config: QortalConfig = default_config,
) -> Dict[str, Any]:
    """
    Provide a concise summary of account information, balance, and owned names.

    Args:
        address: Qortal address to query.
        client: Qortal API client (override for testing).
        config: Configuration providing limits.

    Returns:
        Dict matching the schema defined in DESIGN.md or an error dict.
    """
    if not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    try:
        account_info = await client.fetch_address_info(address)
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
        logger.exception("Unexpected error fetching account info for %s", address)
        return {"error": "Unexpected error while retrieving account data."}

    try:
        balance_payload = await client.fetch_address_balance(address, asset_id=0)
        balance = _normalize_balance(balance_payload)
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
        logger.exception("Unexpected error fetching balance for %s", address)
        return {"error": "Unexpected error while retrieving account balance."}

    names: List[str] = []
    try:
        names_payload = await client.fetch_names_by_owner(address)
        names = _extract_names(names_payload, config.max_names)
    except (InvalidAddressError, AddressNotFoundError):
        # Should not happen due to prior validation, but fail gracefully.
        names = []
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        # Names are optional for this view; log and continue with empty list.
        logger.warning("Name lookup failed for %s", address)
        names = []
    except Exception:
        logger.exception("Unexpected error fetching names for %s", address)
        names = []

    return {
        "address": account_info.get("address", address),
        "publicKey": account_info.get("publicKey"),
        "blocksMinted": _safe_int(account_info.get("blocksMinted")),
        "level": _safe_int(account_info.get("level")),
        "balance": balance,
        "assetBalances": [],
        "names": names,
    }


async def get_balance(
    address: str,
    *,
    asset_id: int = 0,
    client=default_client,
) -> Dict[str, Any]:
    """
    Lightweight balance lookup for a single asset (default QORT assetId=0).
    """
    if not is_valid_qortal_address(address):
        return {"error": "Invalid Qortal address."}

    try:
        parsed_asset_id = int(asset_id)
    except (TypeError, ValueError):
        return {"error": "Invalid asset id."}
    if parsed_asset_id < 0:
        return {"error": "Invalid asset id."}

    try:
        balance_payload = await client.fetch_address_balance(address, asset_id=parsed_asset_id)
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
        logger.exception("Unexpected error fetching balance for %s", address)
        return {"error": "Unexpected error while retrieving balance."}

    return {
        "address": address,
        "assetId": parsed_asset_id,
        "balance": _normalize_balance(balance_payload),
    }


def validate_address(address: str) -> Dict[str, Any]:
    """Utility to validate address format without calling the node."""
    return {"isValid": is_valid_qortal_address(address)}
