"""
Thin HTTP client for whitelisted Qortal Core endpoints.

All methods are read-only and map Qortal errors to internal exceptions that the
tool layer can turn into safe, user-facing messages.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from qortal_mcp.config import QortalConfig, default_config

logger = logging.getLogger(__name__)


class QortalApiError(Exception):
    """Base exception for Qortal API errors."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class InvalidAddressError(QortalApiError):
    """Raised when an address fails validation."""


class AddressNotFoundError(QortalApiError):
    """Raised when an address does not exist on-chain."""


class NameNotFoundError(QortalApiError):
    """Raised when a name is not registered."""


class UnauthorizedError(QortalApiError):
    """Raised when the node rejects the request due to missing auth."""


class NodeUnreachableError(QortalApiError):
    """Raised when the node cannot be reached."""


class QortalApiClient:
    """Async client for the limited Qortal Core API surface."""

    def __init__(
        self,
        config: QortalConfig | None = None,
        *,
        async_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.config = config or default_config
        self._client: Optional[httpx.AsyncClient] = async_client
        self._owns_client = async_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url, timeout=self.config.timeout
            )
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def _map_error(
        self, error_code: str | int | None, status_code: int, message: str | None = None
    ) -> QortalApiError:
        normalized = ""
        if isinstance(error_code, int):
            normalized = str(error_code)
        elif isinstance(error_code, str):
            normalized = error_code.upper()

        message_upper = (message or "").upper()
        lowered_message = (message or "").lower()
        signals = set()
        if normalized:
            signals.add(normalized)
        if message_upper:
            signals.add(message_upper)

        invalid_address_signals = {
            "INVALID_ADDRESS",
            "INVALID_QORTAL_ADDRESS",
            "INVALID_RECIPIENT",
            "102",
        }
        if signals.intersection(invalid_address_signals) or "invalid address" in lowered_message:
            return InvalidAddressError(
                "Invalid Qortal address.",
                code=normalized or message_upper or None,
                status_code=status_code,
            )
        name_unknown_signals = {"NAME_UNKNOWN", "401"}
        if signals.intersection(name_unknown_signals):
            return NameNotFoundError(
                "Name not found.", code=normalized or message_upper or None, status_code=status_code
            )
        block_unknown_signals = {"BLOCK_UNKNOWN", "BLOCK NOT FOUND"}
        if signals.intersection(block_unknown_signals) or "block unknown" in lowered_message:
            return QortalApiError(
                "Block not found.", code=normalized or message_upper or None, status_code=status_code
            )
        invalid_asset_signals = {"INVALID_ASSET_ID", "601"}
        if signals.intersection(invalid_asset_signals):
            return QortalApiError(
                "Asset not found.", code=normalized or message_upper or None, status_code=status_code
            )
        unknown_signals = {"ADDRESS_UNKNOWN", "UNKNOWN_ADDRESS", "124"}
        if signals.intersection(unknown_signals) or "unknown address" in lowered_message:
            return AddressNotFoundError(
                "Address not found on chain.",
                code=normalized or message_upper or None,
                status_code=status_code,
            )
        invalid_public_key_signals = {"INVALID_PUBLIC_KEY"}
        if signals.intersection(invalid_public_key_signals) or "invalid public key" in lowered_message:
            return QortalApiError(
                "Invalid public key.", code=normalized or message_upper or None, status_code=status_code
            )
        invalid_data_signals = {"INVALID_DATA"}
        if signals.intersection(invalid_data_signals) or "invalid data" in lowered_message:
            return QortalApiError(
                "Qortal API error.", code=normalized or message_upper or None, status_code=status_code
            )
        if status_code == 404:
            return QortalApiError(
                "Resource not found.", code=normalized or message_upper or None, status_code=status_code
            )
        if status_code in {401, 403}:
            return UnauthorizedError(
                "Unauthorized or API key required.",
                code=normalized or message_upper or None,
                status_code=status_code,
            )
        return QortalApiError(
            "Qortal API error.", code=normalized or message_upper or None, status_code=status_code
        )

    async def _request(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_api_key: bool = False,
        expect_dict: bool = True,
        expect_json: bool = True,
    ) -> Any:
        client = await self._get_client()
        headers: Dict[str, str] = {}
        if use_api_key and self.config.api_key:
            headers["X-API-KEY"] = self.config.api_key

        try:
            response = await client.get(path, params=params, headers=headers)
        except httpx.RequestError as exc:
            logger.warning("Qortal node unreachable for path %s", path)
            raise NodeUnreachableError("Node unreachable") from exc

        if response.status_code == 401:
            raise UnauthorizedError("Unauthorized or API key required.", status_code=401)

        data: Any = None
        if expect_json or response.status_code >= 400:
            try:
                data = response.json()
            except ValueError:
                data = None

        if response.status_code >= 400:
            error_field: Optional[str | int] = None
            message_field: Optional[str] = None
            if isinstance(data, dict):
                raw_error = data.get("error")
                if isinstance(raw_error, (str, int)):
                    error_field = raw_error
                raw_message = data.get("message")
                if isinstance(raw_message, str):
                    message_field = raw_message
            raise self._map_error(error_field, response.status_code, message=message_field)

        if not expect_json:
            return response.text

        if data is None:
            raise QortalApiError("Unexpected response from node.", status_code=response.status_code)

        if expect_dict and not isinstance(data, dict):
            raise QortalApiError("Unexpected response from node.", status_code=response.status_code)

        return data

    async def fetch_node_status(self) -> Dict[str, Any]:
        """Retrieve node synchronization and connectivity state."""
        return await self._request("/admin/status", use_api_key=True)

    async def fetch_node_info(self) -> Dict[str, Any]:
        """Retrieve node information such as version and uptime."""
        return await self._request("/admin/info", use_api_key=True)

    async def fetch_node_summary(self) -> Dict[str, Any]:
        """Retrieve node summary information."""
        return await self._request("/admin/summary", use_api_key=True)

    async def fetch_node_uptime(self) -> Dict[str, Any]:
        """Retrieve node uptime (if available)."""
        return await self._request("/admin/uptime", use_api_key=True, expect_dict=False)

    async def fetch_address_info(self, address: str) -> Dict[str, Any]:
        """Retrieve base account information for an address."""
        encoded = quote(address, safe="")
        return await self._request(f"/addresses/{encoded}")

    async def fetch_address_balance(self, address: str, asset_id: int = 0) -> Dict[str, Any]:
        """Retrieve balance for an address. Defaults to asset 0 (QORT)."""
        encoded = quote(address, safe="")
        return await self._request(
            f"/addresses/balance/{encoded}", params={"assetId": asset_id}, expect_dict=False
        )

    async def fetch_names_by_owner(self, address: str, *, limit: Optional[int] = None, offset: Optional[int] = None, reverse: Optional[bool] = None) -> Any:
        """Retrieve names owned by the given address."""
        encoded = quote(address, safe="")
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request(f"/names/address/{encoded}", params=params or None, expect_dict=False)

    async def fetch_name_info(self, name: str) -> Dict[str, Any]:
        """Retrieve details for a specific name."""
        encoded = quote(name, safe="")
        return await self._request(f"/names/{encoded}")

    async def fetch_primary_name(self, address: str) -> Dict[str, Any]:
        """Retrieve primary name for an address."""
        encoded = quote(address, safe="")
        return await self._request(f"/names/primary/{encoded}")

    async def search_names(self, query: str, *, prefix: Optional[bool] = None, limit: Optional[int] = None, offset: Optional[int] = None, reverse: Optional[bool] = None) -> Any:
        """Search registered names."""
        params: Dict[str, Any] = {"query": query}
        if prefix is not None:
            params["prefix"] = prefix
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/names/search", params=params, expect_dict=False)

    async def fetch_all_names(self, *, after: Optional[int] = None, limit: Optional[int] = None, offset: Optional[int] = None, reverse: Optional[bool] = None) -> Any:
        """List all names."""
        params: Dict[str, Any] = {}
        if after is not None:
            params["after"] = after
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/names", params=params or None, expect_dict=False)

    async def fetch_names_for_sale(self, *, limit: Optional[int] = None, offset: Optional[int] = None, reverse: Optional[bool] = None) -> Any:
        """List names currently for sale."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/names/forsale", params=params or None, expect_dict=False)

    async def fetch_trade_offers(
        self,
        *,
        limit: int,
        foreign_blockchain: Optional[str] = None,
        offset: Optional[int] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """List open cross-chain trade offers."""
        params: Dict[str, Any] = {"limit": limit}
        if foreign_blockchain:
            params["foreignBlockchain"] = foreign_blockchain
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/crosschain/tradeoffers", params=params, expect_dict=False)

    async def fetch_hidden_trade_offers(
        self,
        *,
        foreign_blockchain: Optional[str] = None,
    ) -> Any:
        """List hidden cross-chain trade offers."""
        params: Dict[str, Any] = {}
        if foreign_blockchain:
            params["foreignBlockchain"] = foreign_blockchain
        return await self._request("/crosschain/tradeoffers/hidden", params=params or None, expect_dict=False)

    async def fetch_trade_detail(self, at_address: str) -> Any:
        """Fetch detailed trade info for a specific AT address."""
        encoded = quote(at_address, safe="")
        return await self._request(f"/crosschain/trade/{encoded}")

    async def fetch_completed_trades(
        self,
        *,
        foreign_blockchain: Optional[str] = None,
        minimum_timestamp: Optional[int] = None,
        buyer_public_key: Optional[str] = None,
        seller_public_key: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """Fetch completed cross-chain trades."""
        params: Dict[str, Any] = {}
        if foreign_blockchain:
            params["foreignBlockchain"] = foreign_blockchain
        if minimum_timestamp is not None:
            params["minimumTimestamp"] = minimum_timestamp
        if buyer_public_key:
            params["buyerPublicKey"] = buyer_public_key
        if seller_public_key:
            params["sellerPublicKey"] = seller_public_key
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/crosschain/trades", params=params or None, expect_dict=False)

    async def fetch_trade_ledger(
        self,
        *,
        public_key: str,
        minimum_timestamp: Optional[int] = None,
    ) -> Any:
        """Fetch trade ledger CSV for a public key."""
        encoded = quote(public_key, safe="")
        params: Dict[str, Any] = {}
        if minimum_timestamp is not None:
            params["minimumTimestamp"] = minimum_timestamp
        return await self._request(f"/crosschain/ledger/{encoded}", params=params or None, expect_dict=False, expect_json=False)

    async def fetch_trade_price(
        self,
        *,
        blockchain: str,
        max_trades: Optional[int] = None,
        inverse: Optional[bool] = None,
    ) -> Any:
        """Fetch estimated trading price."""
        encoded = quote(blockchain, safe="")
        params: Dict[str, Any] = {}
        if max_trades is not None:
            params["maxtrades"] = max_trades
        if inverse is not None:
            params["inverse"] = inverse
        return await self._request(f"/crosschain/price/{encoded}", params=params or None, expect_dict=False)

    async def fetch_block_at_timestamp(self, timestamp: int) -> Any:
        """Fetch block at/just before a timestamp."""
        return await self._request(f"/blocks/timestamp/{timestamp}")

    async def fetch_block_height(self) -> Any:
        """Fetch current blockchain height."""
        return await self._request("/blocks/height", expect_dict=False)

    async def fetch_block_by_height(self, height: int) -> Any:
        """Fetch block info by height."""
        return await self._request(f"/blocks/byheight/{height}")

    async def fetch_block_summaries(self, *, start: int, end: int, count: Optional[int] = None) -> Any:
        """Fetch block summaries in a range."""
        params: Dict[str, Any] = {"start": start, "end": end}
        if count is not None:
            params["count"] = count
        return await self._request("/blocks/summaries", params=params, expect_dict=False)

    async def fetch_block_range(
        self,
        *,
        height: int,
        count: int,
        reverse: Optional[bool] = None,
        include_online_signatures: Optional[bool] = None,
    ) -> Any:
        """Fetch blocks in a range."""
        params: Dict[str, Any] = {"count": count}
        if reverse is not None:
            params["reverse"] = reverse
        if include_online_signatures is not None:
            params["includeOnlineSignatures"] = include_online_signatures
        return await self._request(f"/blocks/range/{height}", params=params, expect_dict=False)

    async def search_transactions(
        self,
        *,
        start_block: Optional[int] = None,
        block_limit: Optional[int] = None,
        tx_types: Optional[List[str | int]] = None,
        address: Optional[str] = None,
        confirmation_status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """Search transactions (read-only)."""
        params: Dict[str, Any] = {}
        if start_block is not None:
            params["startBlock"] = start_block
        if block_limit is not None:
            params["blockLimit"] = block_limit
        if tx_types:
            params["txType"] = tx_types
        if address:
            params["address"] = address
        if confirmation_status:
            params["confirmationStatus"] = confirmation_status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/transactions/search", params=params, expect_dict=False)

    async def fetch_block_by_signature(self, signature: str) -> Any:
        """Fetch block by signature."""
        encoded = quote(signature, safe="")
        return await self._request(f"/blocks/signature/{encoded}")

    async def fetch_block_height_by_signature(self, signature: str) -> Any:
        """Fetch block height from signature."""
        encoded = quote(signature, safe="")
        height_text = await self._request(f"/blocks/height/{encoded}", expect_dict=False, expect_json=False)
        try:
            return int(height_text.strip())
        except (AttributeError, TypeError, ValueError):
            raise QortalApiError("Unexpected response from node.")

    async def fetch_first_block(self) -> Any:
        """Fetch first block."""
        return await self._request("/blocks/first")

    async def fetch_last_block(self) -> Any:
        """Fetch last block."""
        return await self._request("/blocks/last")

    async def fetch_minting_info_by_height(self, height: int) -> Any:
        """Fetch minting info for block height."""
        return await self._request(f"/blocks/byheight/{height}/mintinginfo")

    async def fetch_block_signers(
        self, *, limit: Optional[int] = None, offset: Optional[int] = None, reverse: Optional[bool] = None
    ) -> Any:
        """Fetch list of block signers."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/blocks/signers", params=params or None, expect_dict=False)

    async def fetch_transaction_by_signature(self, signature: str) -> Any:
        """Fetch transaction by signature."""
        encoded = quote(signature, safe="")
        return await self._request(f"/transactions/signature/{encoded}")

    async def fetch_transaction_by_reference(self, reference: str) -> Any:
        """Fetch transaction by reference."""
        encoded = quote(reference, safe="")
        return await self._request(f"/transactions/reference/{encoded}")

    async def fetch_transactions_by_block(
        self,
        signature: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """Fetch transactions for a block signature."""
        encoded = quote(signature, safe="")
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request(f"/transactions/block/{encoded}", params=params or None, expect_dict=False)

    async def fetch_transactions_by_address(
        self,
        address: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        confirmation_status: Optional[str] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """Fetch transactions involving an address."""
        encoded = quote(address, safe="")
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if confirmation_status:
            params["confirmationStatus"] = confirmation_status
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request(f"/transactions/address/{encoded}", params=params or None, expect_dict=False)

    async def fetch_transactions_by_creator(
        self,
        public_key: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        confirmation_status: Optional[str] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """Fetch transactions by creator public key."""
        encoded = quote(public_key, safe="")
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if confirmation_status:
            params["confirmationStatus"] = confirmation_status
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request(f"/transactions/creator/{encoded}", params=params or None, expect_dict=False)

    async def fetch_assets(
        self,
        *,
        include_data: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """List assets."""
        params: Dict[str, Any] = {}
        if include_data is not None:
            params["includeData"] = include_data
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/assets", params=params or None, expect_dict=False)

    async def fetch_asset_info(self, *, asset_id: Optional[int] = None, asset_name: Optional[str] = None) -> Any:
        """Fetch asset info by id or name."""
        params: Dict[str, Any] = {}
        if asset_id is not None:
            params["assetId"] = asset_id
        if asset_name:
            params["assetName"] = asset_name
        return await self._request("/assets/info", params=params or None)

    async def fetch_asset_balances(
        self,
        *,
        addresses: Optional[list[str]] = None,
        asset_ids: Optional[list[int]] = None,
        ordering: Optional[str] = None,
        exclude_zero: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """Fetch asset balances for addresses and/or asset IDs."""
        params: Dict[str, Any] = {}
        if addresses:
            params["address"] = addresses
        if asset_ids:
            params["assetid"] = asset_ids
        if ordering:
            params["ordering"] = ordering
        if exclude_zero is not None:
            params["excludeZero"] = exclude_zero
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/assets/balances", params=params or None, expect_dict=False)

    async def search_qdn(
        self,
        *,
        address: Optional[str] = None,
        service: Optional[str] = None,
        limit: int,
        confirmation_status: Optional[str] = None,
        start_block: Optional[int] = None,
        block_limit: Optional[int] = None,
        tx_group_id: Optional[int] = None,
        name: Optional[str] = None,
        offset: Optional[int] = None,
        reverse: Optional[bool] = None,
    ) -> Any:
        """Search arbitrary/QDN metadata."""
        params: Dict[str, Any] = {"limit": limit}
        if address:
            params["address"] = address
        if service is not None:
            params["service"] = service
        if confirmation_status:
            params["confirmationStatus"] = confirmation_status
        if start_block is not None:
            params["startBlock"] = start_block
        if block_limit is not None:
            params["blockLimit"] = block_limit
        if tx_group_id is not None:
            params["txGroupId"] = tx_group_id
        if name:
            params["name"] = name
        if offset is not None:
            params["offset"] = offset
        if reverse is not None:
            params["reverse"] = reverse
        return await self._request("/arbitrary/search", params=params, expect_dict=False)


default_client = QortalApiClient()
