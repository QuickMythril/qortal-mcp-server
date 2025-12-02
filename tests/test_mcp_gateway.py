from fastapi.testclient import TestClient

from qortal_mcp.config import default_config
from qortal_mcp.server import MCP_SERVER_NAME, MCP_SERVER_VERSION, app
from qortal_mcp.tools.validators import ADDRESS_REGEX


def test_mcp_list_tools():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "list_tools"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert isinstance(data["result"], dict)
    assert "tools" in data["result"]
    tools = data["result"]["tools"]
    assert any(tool["name"] == "validate_address" for tool in tools)
    validate_tool = next(t for t in tools if t["name"] == "validate_address")
    assert "inputSchema" in validate_tool
    assert validate_tool["inputSchema"]["type"] == "object"


def test_mcp_call_tool_validate_address():
    client = TestClient(app)
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "call_tool",
            "params": {"tool": "validate_address", "params": {"address": "bad"}},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 2
    content = data["result"]["content"][0]
    assert content["type"] == "object"
    assert content["object"] == {"isValid": False}


def test_mcp_initialize():
    client = TestClient(app)
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.0.0"},
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 10
    result = data["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["serverInfo"]["name"] == MCP_SERVER_NAME
    assert result["serverInfo"]["version"] == MCP_SERVER_VERSION
    assert result["capabilities"]["tools"]["listChanged"] is False


def test_mcp_tools_list_alias():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 3
    assert isinstance(data["result"], dict)
    assert any(tool["name"] == "get_node_status" for tool in data["result"]["tools"])


def test_mcp_tools_call_alias():
    client = TestClient(app)
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "validate_address", "arguments": {"address": "bad"}},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 4
    content = data["result"]["content"][0]
    assert content["type"] == "object"
    assert content["object"] == {"isValid": False}


def test_mcp_unknown_method_returns_error():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 7, "method": "not_a_real_method"})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == -32601


def test_mcp_invalid_params_type():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 11, "method": "call_tool", "params": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 11
    assert data["error"]["code"] == -32602


def test_mcp_parse_error_invalid_json():
    client = TestClient(app)
    resp = client.post("/mcp", data="{not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == -32700


def test_mcp_missing_method_invalid_request():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 12})
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"]["code"] == -32600


def test_mcp_initialized_notification_ignored():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert resp.status_code == 204
    assert resp.text == ""


def test_mcp_call_tool_missing_name_is_invalid_params():
    client = TestClient(app)
    resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {"arguments": {}}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 13
    assert data["error"]["code"] == -32602


def test_mcp_tool_schemas_include_patterns_and_limits():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 14, "method": "list_tools"})
    assert resp.status_code == 200
    tools = resp.json()["result"]["tools"]

    search_tool = next(t for t in tools if t["name"] == "search_qdn")
    props = search_tool["inputSchema"]["properties"]
    assert props["service"]["maximum"] == 65535
    assert props["limit"]["maximum"] == default_config.max_qdn_results

    names_tool = next(t for t in tools if t["name"] == "get_names_by_address")
    name_props = names_tool["inputSchema"]["properties"]
    assert name_props["address"]["pattern"] == ADDRESS_REGEX.pattern
    assert name_props["limit"]["maximum"] == default_config.max_names


def test_mcp_wraps_list_results_into_object_container(monkeypatch):
    async def fake_call_tool(name, params=None):
        return [{"foo": "bar"}, {"baz": "qux"}]

    monkeypatch.setattr("qortal_mcp.server.mcp.call_tool", fake_call_tool)

    client = TestClient(app)
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {"name": "list_trade_offers", "arguments": {}},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    content = data["result"]["content"][0]
    assert content["type"] == "object"
    assert content["object"]["items"] == [{"foo": "bar"}, {"baz": "qux"}]
