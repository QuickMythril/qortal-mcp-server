import pytest
from fastapi.testclient import TestClient

from qortal_mcp.server import app
from qortal_mcp.tools.names import get_name_info, get_names_by_address


@pytest.mark.asyncio
async def test_get_name_info_invalid_name():
    result = await get_name_info("!!bad")
    assert result == {"error": "Invalid name."}


@pytest.mark.asyncio
async def test_names_by_address_invalid_short_circuit():
    class FailClient:
        async def fetch_names_by_owner(self, *_args, **_kwargs):
            pytest.fail("Should not call Core for invalid address")

    result = await get_names_by_address("bad", client=FailClient())
    assert result == {"error": "Invalid Qortal address."}


def test_metrics_tool_success_and_error_counts(monkeypatch):
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
    assert data["result"].get("error")


def test_json_log_mode_initialization(monkeypatch):
    # Ensure setting log format to json doesn't crash import/handlers
    monkeypatch.setenv("QORTAL_MCP_LOG_FORMAT", "json")
    import importlib
    import qortal_mcp.server as server_mod

    importlib.reload(server_mod)
