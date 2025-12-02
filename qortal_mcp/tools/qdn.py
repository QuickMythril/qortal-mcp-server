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
        "service": raw.get("service"),
        "timestamp": raw.get("timestamp"),
        "publisher": raw.get("publisher") or raw.get("name"),
    }


SERVICE_ID_TO_NAME: Dict[int, str] = {
    1: "AUTO_UPDATE",
    100: "ARBITRARY_DATA",
    120: "QCHAT_ATTACHMENT",
    121: "QCHAT_ATTACHMENT_PRIVATE",
    130: "ATTACHMENT",
    131: "ATTACHMENT_PRIVATE",
    140: "FILE",
    141: "FILE_PRIVATE",
    150: "FILES",
    160: "CHAIN_DATA",
    200: "WEBSITE",
    300: "GIT_REPOSITORY",
    400: "IMAGE",
    401: "IMAGE_PRIVATE",
    410: "THUMBNAIL",
    420: "QCHAT_IMAGE",
    500: "VIDEO",
    501: "VIDEO_PRIVATE",
    600: "AUDIO",
    601: "AUDIO_PRIVATE",
    610: "QCHAT_AUDIO",
    620: "QCHAT_VOICE",
    630: "VOICE",
    631: "VOICE_PRIVATE",
    640: "PODCAST",
    700: "BLOG",
    777: "BLOG_POST",
    778: "BLOG_COMMENT",
    800: "DOCUMENT",
    801: "DOCUMENT_PRIVATE",
    900: "LIST",
    910: "PLAYLIST",
    1000: "APP",
    1100: "METADATA",
    1110: "JSON",
    1200: "GIF_REPOSITORY",
    1300: "STORE",
    1310: "PRODUCT",
    1330: "OFFER",
    1340: "COUPON",
    1400: "CODE",
    1410: "PLUGIN",
    1420: "EXTENSION",
    1500: "GAME",
    1510: "ITEM",
    1600: "NFT",
    1700: "DATABASE",
    1710: "SNAPSHOT",
    1800: "COMMENT",
    1810: "CHAIN_COMMENT",
    1900: "MAIL",
    1901: "MAIL_PRIVATE",
    1910: "MESSAGE",
    1911: "MESSAGE_PRIVATE",
}

SERVICE_NAMES = set(SERVICE_ID_TO_NAME.values())


def _normalize_service(service: Optional[Any]) -> Optional[str]:
    if service is None:
        return None
    if isinstance(service, str):
        candidate = service.strip().upper()
        if candidate in SERVICE_NAMES:
            return candidate
        try:
            numeric = int(candidate)
        except ValueError:
            return None
        return SERVICE_ID_TO_NAME.get(numeric)
    try:
        numeric = int(service)
    except (TypeError, ValueError):
        return None
    return SERVICE_ID_TO_NAME.get(numeric)


def _normalize_confirmation_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return "CONFIRMED"
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"CONFIRMED", "UNCONFIRMED", "BOTH"}:
            return normalized
    return None


async def search_qdn(
    *,
    address: Optional[str] = None,
    service: Optional[Any] = None,
    limit: Optional[int] = None,
    confirmation_status: Optional[str] = None,
    start_block: Optional[int] = None,
    block_limit: Optional[int] = None,
    tx_group_id: Optional[int] = None,
    name: Optional[str] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
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

    normalized_service = _normalize_service(service)
    if service is not None and normalized_service is None:
        return {"error": "Invalid service code or name."}

    normalized_status = _normalize_confirmation_status(confirmation_status)
    if normalized_status is None:
        return {"error": "Invalid confirmation status."}

    def _parse_non_negative(value: Optional[int], field: str) -> Optional[int]:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError(field)
        if parsed < 0:
            raise ValueError(field)
        return parsed

    try:
        parsed_start_block = _parse_non_negative(start_block, "startBlock")
        parsed_block_limit = _parse_non_negative(block_limit, "blockLimit")
        parsed_tx_group_id = _parse_non_negative(tx_group_id, "txGroupId")
    except ValueError:
        return {"error": "Invalid numeric search parameter."}

    if (parsed_start_block is not None or parsed_block_limit is not None) and normalized_status != "CONFIRMED":
        return {"error": "Block range search requires confirmationStatus=CONFIRMED."}

    # If no address is provided, force a bounded block window to avoid unbounded scans.
    if not address and (parsed_start_block is None or parsed_block_limit is None):
        return {"error": "start_block and block_limit are required when address is not provided."}

    # If only address is provided (no service), also require a bounded block window to avoid wide scans.
    if address and normalized_service is None and (parsed_start_block is None or parsed_block_limit is None):
        return {"error": "start_block and block_limit are required when service is not provided."}

    effective_offset = clamp_limit(offset, default=0, max_value=config.max_qdn_results)
    effective_limit = clamp_limit(
        limit, default=config.default_qdn_results, max_value=config.max_qdn_results
    )

    name_filter = name.strip() if isinstance(name, str) else None
    if name_filter == "":
        name_filter = None

    try:
        raw_results = await client.search_qdn(
            address=address,
            service=normalized_service,
            limit=effective_limit,
            confirmation_status=normalized_status,
            start_block=parsed_start_block,
            block_limit=parsed_block_limit,
            tx_group_id=parsed_tx_group_id,
            name=name_filter,
            offset=effective_offset,
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
        logger.exception("Unexpected error during QDN search")
        return {"error": "Unexpected error while performing search."}

    results: List[Dict[str, Any]] = []
    if isinstance(raw_results, list):
        for entry in raw_results[:effective_limit]:
            if isinstance(entry, dict):
                results.append(_normalize_search_entry(entry))

    return results[:effective_limit]
