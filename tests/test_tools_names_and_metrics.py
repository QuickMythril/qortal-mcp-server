import pytest
from fastapi.testclient import TestClient

from qortal_mcp.server import app
from qortal_mcp.tools.names import get_name_info, get_names_by_address, _truncate_data
from qortal_mcp.qortal_api.client import NameNotFoundError, UnauthorizedError, NodeUnreachableError


@pytest.mark.asyncio
async def test_get_name_info_invalid_name():
    result = await get_name_info("!!bad")
    assert result == {"error": "Invalid name."}


@pytest.mark.asyncio
async def test_get_name_info_happy_path():
    class StubClient:
        async def fetch_name_info(self, name):
            return {
                "name": name,
                "owner": "QOWNER",
                "data": "x" * 10,
                "isForSale": False,
                "salePrice": None,
            }

    result = await get_name_info("good-name", client=StubClient())
    assert result["name"] == "good-name"
    assert result["owner"] == "QOWNER"
    assert result["data"].startswith("x")


@pytest.mark.asyncio
async def test_get_name_info_error_mapping():
    class StubClient:
        async def fetch_name_info(self, *_args, **_kwargs):
            raise NameNotFoundError("missing")

    result = await get_name_info("good-name", client=StubClient())
    assert result == {"error": "Name not found."}


@pytest.mark.asyncio
async def test_get_name_info_unauthorized_and_unreachable():
    class UnauthorizedClient:
        async def fetch_name_info(self, *_args, **_kwargs):
            raise UnauthorizedError("nope")

    class UnreachableClient:
        async def fetch_name_info(self, *_args, **_kwargs):
            raise NodeUnreachableError("down")

    assert await get_name_info("good-name", client=UnauthorizedClient()) == {
        "error": "Unauthorized or API key required."
    }
    assert await get_name_info("good-name", client=UnreachableClient()) == {"error": "Node unreachable"}


def test_truncate_data():
    assert _truncate_data(None, 5) is None
    assert _truncate_data("short", 10) == "short"
    long_text = "x" * 50
    truncated = _truncate_data(long_text, 20)
    assert truncated.endswith("... (truncated)")


@pytest.mark.asyncio
async def test_names_by_address_invalid_short_circuit():
    class FailClient:
        async def fetch_names_by_owner(self, *_args, **_kwargs):
            pytest.fail("Should not call Core for invalid address")

    result = await get_names_by_address("bad", client=FailClient())
    assert result == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_names_by_address_happy_path_with_limit():
    class StubClient:
        async def fetch_names_by_owner(self, *_args, **_kwargs):
            return ["a", "b", "c", "d"]

    result = await get_names_by_address("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", limit=2, client=StubClient())
    assert result["names"] == ["a", "b"]  # clamped


@pytest.mark.asyncio
async def test_names_by_address_error_mapping():
    class StubClient:
        async def fetch_names_by_owner(self, *_args, **_kwargs):
            raise UnauthorizedError("nope")

    result = await get_names_by_address("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Unauthorized or API key required."}


@pytest.mark.asyncio
async def test_names_by_address_not_found():
    class StubClient:
        async def fetch_names_by_owner(self, *_args, **_kwargs):
            raise NameNotFoundError("missing")

    result = await get_names_by_address("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_names_by_address_unreachable():
    class StubClient:
        async def fetch_names_by_owner(self, *_args, **_kwargs):
            raise NodeUnreachableError("down")

    result = await get_names_by_address("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV", client=StubClient())
    assert result == {"error": "Node unreachable"}


def test_metrics_tool_success_and_error_counts(monkeypatch):
    from qortal_mcp import server as server_mod

    async def always_allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(server_mod.rate_limiter, "allow", always_allow)
    client = TestClient(app)
    # Successful validate
    client.get("/tools/validate_address/QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV")
    # Erroring name_info (invalid)
    client.get("/tools/name_info/!!bad")
    data = client.get("/metrics").json()
    assert data.get("tool_success", {}).get("validate_address", 0) >= 1
    assert data.get("tool_error", {}).get("get_name_info", 0) >= 1


def test_per_tool_rate_limit_enforced(monkeypatch):
    from qortal_mcp import server as server_mod

    # Override limiter for a specific tool to always deny after first call
    call_count = {"n": 0}

    async def allow_with_limit(key):
        if key == "get_balance":
            call_count["n"] += 1
            return call_count["n"] == 1
        return True

    monkeypatch.setattr(server_mod.rate_limiter, "allow", allow_with_limit)
    client = TestClient(app)
    first = client.get("/tools/balance/QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV")
    second = client.get("/tools/balance/QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV")
    assert first.status_code != 429
    assert second.status_code == 429


def test_mcp_unknown_tool_returns_error():
    client = TestClient(app)
    resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 5, "method": "call_tool", "params": {"tool": "nope", "params": {}}},
    )
    assert resp.status_code == 200
    data = resp.json()
    result = data["result"]
    assert result.get("isError") is True
    content = result["content"][0]
    assert content["type"] == "text"
    assert "Unknown tool" in content["text"]


def test_json_log_mode_initialization(monkeypatch):
    # Ensure setting log format to json doesn't crash import/handlers
    monkeypatch.setenv("QORTAL_MCP_LOG_FORMAT", "json")
    import importlib
    import qortal_mcp.server as server_mod

    importlib.reload(server_mod)
