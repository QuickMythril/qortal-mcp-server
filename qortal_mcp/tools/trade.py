"""Trade Portal tools."""

from __future__ import annotations

import logging
import re
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

BASE58_REGEX = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")


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


def _is_base58(value: str, *, min_len: int, max_len: int) -> bool:
    if not value or not isinstance(value, str):
        return False
    stripped = value.strip()
    if len(stripped) < min_len or len(stripped) > max_len:
        return False
    return bool(BASE58_REGEX.fullmatch(stripped))


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


async def list_hidden_trade_offers(
    *,
    foreign_blockchain: Optional[str] = None,
    client=default_client,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """List hidden cross-chain trade offers (failed offers)."""
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
        raw_offers = await client.fetch_hidden_trade_offers(foreign_blockchain=normalized_foreign)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching hidden trade offers")
        return {"error": "Unexpected error while retrieving hidden trade offers."}

    offers: List[Dict[str, Any]] = []
    if isinstance(raw_offers, list):
        for entry in raw_offers:
            if isinstance(entry, dict):
                offers.append(_normalize_offer(entry))
    return offers


async def get_trade_detail(
    *,
    at_address: str,
    client=default_client,
) -> Dict[str, Any]:
    """Fetch detailed trade info for a specific AT address."""
    if not at_address or not isinstance(at_address, str):
        return {"error": "AT address is required."}
    if not _is_base58(at_address, min_len=32, max_len=36):
        return {"error": "Invalid AT address."}
    try:
        raw = await client.fetch_trade_detail(at_address)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching trade detail for %s", at_address)
        return {"error": "Unexpected error while retrieving trade detail."}

    if isinstance(raw, dict):
        return _normalize_offer(raw)
    return {"error": "Unexpected response from node."}


async def list_completed_trades(
    *,
    foreign_blockchain: Optional[str] = None,
    minimum_timestamp: Optional[int] = None,
    buyer_public_key: Optional[str] = None,
    seller_public_key: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    reverse: Optional[bool] = None,
    client=default_client,
    config: QortalConfig = default_config,
) -> List[Dict[str, Any]] | Dict[str, str]:
    """List completed cross-chain trades."""
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

    if minimum_timestamp is not None:
        try:
            minimum_timestamp = int(minimum_timestamp)
        except (TypeError, ValueError):
            return {"error": "Invalid minimumTimestamp."}
        if minimum_timestamp <= 0:
            return {"error": "Invalid minimumTimestamp."}

    def _valid_public_key(value: Optional[str]) -> bool:
        if value is None:
            return True
        return _is_base58(value, min_len=43, max_len=45)

    if not _valid_public_key(buyer_public_key) or not _valid_public_key(seller_public_key):
        return {"error": "Invalid public key."}

    effective_limit = clamp_limit(limit, default=config.default_trade_offers, max_value=config.max_trade_offers)
    effective_offset = clamp_limit(offset, default=0, max_value=config.max_trade_offers)

    try:
        raw_trades = await client.fetch_completed_trades(
            foreign_blockchain=normalized_foreign,
            minimum_timestamp=minimum_timestamp,
            buyer_public_key=buyer_public_key,
            seller_public_key=seller_public_key,
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
        logger.exception("Unexpected error fetching completed trades")
        return {"error": "Unexpected error while retrieving completed trades."}

    results: List[Dict[str, Any]] = []
    if isinstance(raw_trades, list):
        for entry in raw_trades[:effective_limit]:
            if isinstance(entry, dict):
                # Keep the raw summary structure; normalize only key fields.
                results.append(
                    {
                        "tradeAddress": entry.get("qortalAtAddress") or entry.get("tradeAddress"),
                        "foreignBlockchain": entry.get("foreignBlockchain"),
                        "tradeTimestamp": entry.get("tradeTimestamp") or entry.get("timestamp"),
                        "qortAmount": entry.get("qortAmount"),
                        "expectedForeignAmount": entry.get("expectedForeignAmount") or entry.get("expectedForeign"),
                        "mode": entry.get("mode"),
                    }
                )
    return results[:effective_limit]


async def get_trade_ledger(
    *,
    public_key: str,
    minimum_timestamp: Optional[int] = None,
    client=default_client,
) -> Dict[str, Any]:
    """Fetch trade ledger entries CSV for a public key (returns raw payload)."""
    if not public_key or not isinstance(public_key, str):
        return {"error": "Public key is required."}
    if not _is_base58(public_key, min_len=43, max_len=45):
        return {"error": "Invalid public key."}
    if minimum_timestamp is not None:
        try:
            minimum_timestamp = int(minimum_timestamp)
        except (TypeError, ValueError):
            return {"error": "Invalid minimumTimestamp."}
        if minimum_timestamp <= 0:
            return {"error": "Invalid minimumTimestamp."}
    try:
        raw = await client.fetch_trade_ledger(public_key=public_key, minimum_timestamp=minimum_timestamp)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching trade ledger for %s", public_key)
        return {"error": "Unexpected error while retrieving trade ledger."}

    return raw if isinstance(raw, dict) else {"ledger": raw}


async def get_trade_price(
    *,
    blockchain: str,
    max_trades: Optional[int] = None,
    inverse: Optional[bool] = None,
    client=default_client,
) -> Dict[str, Any]:
    """Fetch estimated trading price."""
    if not blockchain or not isinstance(blockchain, str):
        return {"error": "Blockchain is required."}
    normalized = blockchain.strip().upper()
    allowed_blockchains = {
        "BITCOIN",
        "LITECOIN",
        "DOGECOIN",
        "DIGIBYTE",
        "RAVENCOIN",
        "PIRATECHAIN",
    }
    if normalized not in allowed_blockchains:
        return {"error": "Invalid blockchain."}
    if max_trades is not None:
        try:
            max_trades = int(max_trades)
        except (TypeError, ValueError):
            return {"error": "Invalid maxtrades."}
        if max_trades <= 0:
            return {"error": "Invalid maxtrades."}
    try:
        raw = await client.fetch_trade_price(blockchain=normalized, max_trades=max_trades, inverse=inverse)
    except UnauthorizedError:
        return {"error": "Unauthorized or API key required."}
    except NodeUnreachableError:
        return {"error": "Node unreachable"}
    except QortalApiError:
        return {"error": "Qortal API error."}
    except Exception:
        logger.exception("Unexpected error fetching trade price for %s", blockchain)
        return {"error": "Unexpected error while retrieving trade price."}

    if isinstance(raw, (int, float)):
        return {"price": raw}
    if isinstance(raw, dict) and "price" in raw:
        return {"price": raw.get("price")}
    return {"error": "Unexpected response from node."}
