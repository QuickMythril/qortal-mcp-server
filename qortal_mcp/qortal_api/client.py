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

    async def fetch_names_by_owner(self, address: str) -> Any:
        """Retrieve names owned by the given address."""
        encoded = quote(address, safe="")
        return await self._request(f"/names/address/{encoded}", expect_dict=False)

    async def fetch_name_info(self, name: str) -> Dict[str, Any]:
        """Retrieve details for a specific name."""
        encoded = quote(name, safe="")
        return await self._request(f"/names/{encoded}")

    async def fetch_trade_offers(self, *, limit: int) -> Any:
        """List open cross-chain trade offers."""
        return await self._request("/crosschain/tradeoffers", params={"limit": limit}, expect_dict=False)

    async def search_qdn(
        self,
        *,
        address: Optional[str] = None,
        service: Optional[int] = None,
        limit: int,
    ) -> Any:
        """Search arbitrary/QDN metadata."""
        params: Dict[str, Any] = {"limit": limit}
        if address:
            params["address"] = address
        if service is not None:
            params["service"] = service
        return await self._request("/arbitrary/search", params=params, expect_dict=False)


default_client = QortalApiClient()
