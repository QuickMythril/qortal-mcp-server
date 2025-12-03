"""Account-related tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import (
    AddressNotFoundError,
    InvalidAddressError,
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import is_valid_qortal_address, parse_int_list

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


async def _resolve_asset_name(client, asset_id: int) -> Optional[str]:
    try:
        info = await client.fetch_asset_info(asset_id=asset_id)
    except Exception:
        return None
    if isinstance(info, dict):
        name = info.get("name") or info.get("assetName")
        if isinstance(name, str):
            return name
    return None


async def _fetch_asset_balances(
    *,
    client,
    address: str,
    asset_ids: Optional[List[int]],
    config: QortalConfig,
) -> List[Dict[str, Any]]:
    max_assets = config.max_asset_overview
    parsed_ids = parse_int_list(asset_ids, max_items=max_assets) if asset_ids is not None else None

    if asset_ids is not None and parsed_ids is None:
        return {"error": "Invalid asset_ids; must be 1 to %d integers." % max_assets}

    # If explicit IDs provided
    if parsed_ids:
        balances: List[Dict[str, Any]] = []
        for asset_id in parsed_ids[:max_assets]:
            try:
                raw_balance = await client.fetch_address_balance(address, asset_id=asset_id)
                balance_str = _normalize_balance(raw_balance)
                name = await _resolve_asset_name(client, asset_id)
                entry: Dict[str, Any] = {
                    "assetId": asset_id,
                    "balance": balance_str,
                }
                if name:
                    entry["name"] = name
                balances.append(entry)
            except InvalidAddressError:
                return [{"error": "Invalid Qortal address."}]
            except AddressNotFoundError:
                return [{"error": "Address not found on chain."}]
            except UnauthorizedError:
                return [{"error": "Unauthorized or API key required."}]
            except NodeUnreachableError:
                return [{"error": "Node unreachable"}]
            except QortalApiError:
                balances.append({"assetId": asset_id, "error": "Asset not found."})
            except Exception:
                logger.exception("Unexpected error fetching asset balance for asset %s", asset_id)
                balances.append({"assetId": asset_id, "error": "Unexpected error."})
        return balances[:max_assets]

    # No explicit IDs: fetch top-N balances for this address
    try:
        raw = await client.fetch_asset_balances(
            addresses=[address],
            limit=config.default_asset_overview,
            exclude_zero=True,
            ordering="ASSET_BALANCE_ACCOUNT",
        )
    except InvalidAddressError:
        return [{"error": "Invalid Qortal address."}]
    except AddressNotFoundError:
        return [{"error": "Address not found on chain."}]
    except UnauthorizedError:
        return [{"error": "Unauthorized or API key required."}]
    except NodeUnreachableError:
        return [{"error": "Node unreachable"}]
    except QortalApiError:
        return [{"error": "Qortal API error."}]
    except Exception:
        logger.exception("Unexpected error fetching asset balances for %s", address)
        return [{"error": "Unexpected error while retrieving asset balances."}]

    results: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw[:max_assets]:
            if not isinstance(entry, dict):
                continue
            asset_id = entry.get("assetId") or entry.get("assetid") or entry.get("assetID")
            try:
                parsed_asset_id = int(asset_id)
            except (TypeError, ValueError):
                continue
            balance_value = entry.get("balance") or entry.get("assetBalance")
            normalized_balance = _normalize_balance(balance_value)
            results.append({"assetId": parsed_asset_id, "balance": normalized_balance})

    # Optionally resolve names for the collected asset IDs
    for item in results:
        name = await _resolve_asset_name(client, item["assetId"])
        if name:
            item["name"] = name

    return results[:max_assets]


async def get_account_overview(
    address: str,
    *,
    include_assets: bool = False,
    asset_ids: Optional[List[int]] = None,
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

    asset_balances: List[Dict[str, Any]] = []
    if include_assets:
        assets_result = await _fetch_asset_balances(
            client=client,
            address=address,
            asset_ids=asset_ids,
            config=config,
        )
        if isinstance(assets_result, dict) and assets_result.get("error"):
            return assets_result
        if isinstance(assets_result, list):
            asset_balances = assets_result

    return {
        "address": account_info.get("address", address),
        "publicKey": account_info.get("publicKey"),
        "blocksMinted": _safe_int(account_info.get("blocksMinted")),
        "level": _safe_int(account_info.get("level")),
        "balance": balance,
        "assetBalances": asset_balances[: config.max_asset_overview],
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
