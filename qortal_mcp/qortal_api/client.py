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

        lowered_message = (message or "").lower()

        invalid_address_signals = {
            "INVALID_ADDRESS",
            "INVALID_QORTAL_ADDRESS",
            "INVALID_RECIPIENT",
            "102",
        }
        if normalized in invalid_address_signals or "invalid address" in lowered_message:
            return InvalidAddressError(
                "Invalid Qortal address.", code=normalized or None, status_code=status_code
            )
        name_unknown_signals = {"NAME_UNKNOWN", "401"}
        if normalized in name_unknown_signals:
            return NameNotFoundError(
                "Name not found.", code=normalized or None, status_code=status_code
            )
        unknown_signals = {"ADDRESS_UNKNOWN", "UNKNOWN_ADDRESS", "124"}
        if normalized in unknown_signals or "unknown address" in lowered_message:
            return AddressNotFoundError(
                "Address not found on chain.", code=normalized or None, status_code=status_code
            )
        if status_code == 404:
            return QortalApiError("Resource not found.", code=normalized or None, status_code=status_code)
        if status_code in {401, 403}:
            return UnauthorizedError(
                "Unauthorized or API key required.", code=normalized or None, status_code=status_code
            )
        return QortalApiError(
            "Qortal API error.", code=normalized or None, status_code=status_code
        )

    async def _request(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_api_key: bool = False,
        expect_dict: bool = True,
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

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Unexpected non-JSON response from node at %s", path)
            raise QortalApiError("Unexpected response from node.", status_code=response.status_code) from exc

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
