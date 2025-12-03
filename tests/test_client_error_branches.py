import pytest

from qortal_mcp.qortal_api.client import QortalApiClient, QortalApiError, UnauthorizedError


class MockResponse:
    def __init__(self, status_code: int, json_body=None, text_body: str | None = None):
        self.status_code = status_code
        self._json = json_body
        self.text = text_body or ""

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class MockAsyncClient:
    def __init__(self, responses):
        self.responses = responses

    async def get(self, path, params=None, headers=None):
        if not self.responses:
            raise RuntimeError("No responses")
        return self.responses.pop(0)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_request_unexpected_json_and_401():
    mock = MockAsyncClient([MockResponse(200, json_body=None)])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(QortalApiError):
        await client.fetch_name_info("alice")

    mock = MockAsyncClient([MockResponse(401, {"error": "UNAUTHORIZED"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(UnauthorizedError):
        await client.fetch_node_info()


@pytest.mark.asyncio
async def test_map_error_default_paths():
    mock = MockAsyncClient([MockResponse(404, {"error": "other"})])
    client = QortalApiClient(async_client=mock)
    with pytest.raises(QortalApiError) as excinfo:
        await client.fetch_asset_info(asset_id=1)
    assert "Resource not found." in str(excinfo.value)

