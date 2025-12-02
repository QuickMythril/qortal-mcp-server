"""Trade Portal tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qortal_mcp.config import QortalConfig, default_config
from qortal_mcp.qortal_api import (
    NodeUnreachableError,
    QortalApiError,
    UnauthorizedError,
    default_client,
)
from qortal_mcp.tools.validators import clamp_limit

logger = logging.getLogger(__name__)


def _normalize_offer(raw_offer: Dict[str, Any]) -> Dict[str, Any]:
    # The Core response varies by version; prefer the most specific fields and
    # fall back to legacy names to avoid nulls.
    trade_address = raw_offer.get("tradeAddress") or raw_offer.get("qortalCreatorTradeAddress") or raw_offer.get(
        "qortalAtAddress"
    )
    creator = raw_offer.get("creator") or raw_offer.get("qortalCreator")
    timestamp = raw_offer.get("timestamp") or raw_offer.get("creationTimestamp")
    foreign_currency = raw_offer.get("foreignCurrency") or raw_offer.get("foreignBlockchain")
    expected_foreign = (
        raw_offer.get("expectedForeign")
        or raw_offer.get("expectedForeignAmount")
        or raw_offer.get("expectedBitcoin")
        or raw_offer.get("foreignAmount")
    )

    return {
        "tradeAddress": trade_address,
        "creator": creator,
        "offeringQort": str(raw_offer.get("qortAmount") or raw_offer.get("offeringQort") or "0"),
        "expectedForeign": str(expected_foreign or "0"),
        "foreignCurrency": foreign_currency,
        "mode": raw_offer.get("mode"),
        "timestamp": timestamp,
    }


async def list_trade_offers(
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    foreign_blockchain: Optional[str] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """
    List open cross-chain trade offers.
    """
    effective_limit = clamp_limit(
        limit,
        default=config.default_trade_offers,
        max_value=config.max_trade_offers,
    )
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_trade_offers)

    allowed_blockchains = {
        "BITCOIN",
        "LITECOIN",
        "DOGECOIN",
        "DIGIBYTE",
        "RAVENCOIN",
        "PIRATECHAIN",
    }
    normalized_foreign: Optional[str] = None
    if foreign_blockchain:
        normalized_foreign = foreign_blockchain.strip().upper()
        if normalized_foreign not in allowed_blockchains:
            return {"error": "Invalid foreign blockchain."}

    try:
        raw_offers = await client.fetch_trade_offers(
            limit=effective_limit,
            foreign_blockchain=normalized_foreign,
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
        logger.exception("Unexpected error fetching trade offers")
        return {"error": "Unexpected error while retrieving trade offers."}

    offers: List[Dict[str, Any]] = []
    if isinstance(raw_offers, list):
        for entry in raw_offers[:effective_limit]:
            if isinstance(entry, dict):
                offers.append(_normalize_offer(entry))
    return offers[:effective_limit]
