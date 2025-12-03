import pytest

from qortal_mcp.qortal_api.client import (
    NodeUnreachableError,
    QortalApiClient,
    QortalApiError,
    UnauthorizedError,
    AddressNotFoundError,
)


class MockResponse:
    def __init__(self, status_code: int, json_body=None, text_body: str | None = None):
        self.status_code = status_code
        self._json = json_body
        self.text = text_body

    def json(self):
        if self._json is None:
            raise ValueError("no json")
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
async def test_client_expect_text_success():
    mock = MockAsyncClient([MockResponse(200, json_body="ok")])
    client = QortalApiClient(async_client=mock)
    result = await client.fetch_node_uptime()
    assert result == "ok"


@pytest.mark.asyncio
async def test_client_non_json_response_error():
    mock = MockAsyncClient([MockResponse(200, json_body=None, text_body="raw")])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(QortalApiError):
        await client.fetch_node_status()


@pytest.mark.asyncio
async def test_client_unauthorized_mapping():
    mock = MockAsyncClient([MockResponse(401, {"error": "UNAUTHORIZED"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(UnauthorizedError):
        await client.fetch_node_status()


@pytest.mark.asyncio
async def test_client_node_unreachable(monkeypatch):
    import httpx

    class FailClient:
        async def get(self, *_args, **_kwargs):
            raise httpx.RequestError("down")

        async def aclose(self):
            return None

    client = QortalApiClient(async_client=FailClient())
    with pytest.raises(NodeUnreachableError):
        await client.fetch_node_status()


@pytest.mark.asyncio
async def test_client_block_not_found_mapping():
    mock = MockAsyncClient([MockResponse(404, {"error": "BLOCK_UNKNOWN"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(QortalApiError) as excinfo:
        await client.fetch_block_by_height(1)
    assert "Block not found." in str(excinfo.value)


@pytest.mark.asyncio
async def test_client_invalid_address_and_unknown_address():
    mock = MockAsyncClient([MockResponse(400, {"error": "INVALID_ADDRESS"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(QortalApiError):
        await client.fetch_address_info("bad")

    mock = MockAsyncClient([MockResponse(404, {"error": "ADDRESS_UNKNOWN"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(AddressNotFoundError):
        await client.fetch_address_info("Q...")


@pytest.mark.asyncio
async def test_client_invalid_data_error():
    mock = MockAsyncClient([MockResponse(500, {"error": "INVALID_DATA", "message": "bad"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(QortalApiError):
        await client.fetch_node_info()
