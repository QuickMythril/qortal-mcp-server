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
    return {
        "tradeAddress": raw_offer.get("tradeAddress"),
        "creator": raw_offer.get("creator"),
        "offeringQort": str(raw_offer.get("qortAmount") or raw_offer.get("offeringQort") or "0"),
        "expectedForeign": str(
            raw_offer.get("expectedForeign") or raw_offer.get("foreignAmount") or "0"
        ),
        "foreignCurrency": raw_offer.get("foreignCurrency"),
        "mode": raw_offer.get("mode"),
        "timestamp": raw_offer.get("timestamp"),
    }


async def list_trade_offers(
    *,
    limit: Optional[int] = None,
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

    try:
        raw_offers = await client.fetch_trade_offers(limit=effective_limit)
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

