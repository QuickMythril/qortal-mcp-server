import pytest

from qortal_mcp.qortal_api.client import (
    AddressNotFoundError,
    InvalidAddressError,
    NameNotFoundError,
    NodeUnreachableError,
    QortalApiClient,
    UnauthorizedError,
    QortalApiError,
)


class MockResponse:
    def __init__(self, status_code: int, json_body):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json


class MockAsyncClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, path, params=None, headers=None):
        self.calls.append({"path": path, "params": params, "headers": headers})
        if not self.responses:
            raise RuntimeError("No mock responses")
        return self.responses.pop(0)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_invalid_address_mapping():
    mock = MockAsyncClient([MockResponse(400, {"error": "INVALID_ADDRESS"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(InvalidAddressError):
        await client.fetch_address_info("bad")


@pytest.mark.asyncio
async def test_address_not_found_mapping():
    mock = MockAsyncClient([MockResponse(404, {"error": "ADDRESS_UNKNOWN"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(AddressNotFoundError):
        await client.fetch_address_info("Q...")


@pytest.mark.asyncio
async def test_name_not_found_mapping():
    mock = MockAsyncClient([MockResponse(404, {"error": "NAME_UNKNOWN"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(NameNotFoundError):
        await client.fetch_name_info("missing")


@pytest.mark.asyncio
async def test_unauthorized_mapping():
    mock = MockAsyncClient([MockResponse(401, {"error": "UNAUTHORIZED"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(UnauthorizedError):
        await client.fetch_node_status()


@pytest.mark.asyncio
async def test_unexpected_response():
    mock = MockAsyncClient([MockResponse(200, ["unexpected"])])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(Exception):
        await client.fetch_node_status()


@pytest.mark.asyncio
async def test_server_error_maps_to_generic():
    mock = MockAsyncClient([MockResponse(500, {"error": "INTERNAL_ERROR"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(QortalApiError) as excinfo:
        await client.fetch_node_status()
    assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_path_encoding_and_params(monkeypatch):
    captured = {}

    class CaptureClient:
        async def get(self, path, params=None, headers=None):
            captured["path"] = path
            captured["params"] = params
            return MockResponse(200, {})

        async def aclose(self):
            return None

    client = QortalApiClient(async_client=CaptureClient())
    await client.fetch_address_balance("Q address/with space", asset_id=7)
    assert "%20" in captured["path"] or "%2F" in captured["path"]
    assert captured["params"]["assetId"] == 7
