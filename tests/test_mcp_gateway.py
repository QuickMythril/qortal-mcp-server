from fastapi.testclient import TestClient

from qortal_mcp.server import MCP_SERVER_NAME, MCP_SERVER_VERSION, app


def test_mcp_list_tools():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "list_tools"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert isinstance(data["result"], list)
    assert any(tool["name"] == "validate_address" for tool in data["result"])


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
    assert data["result"] == {"isValid": False}


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
    assert isinstance(data["result"], list)
    assert any(tool["name"] == "get_node_status" for tool in data["result"])


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
    assert data["result"] == {"isValid": False}


def test_mcp_unknown_method_returns_error():
    client = TestClient(app)
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 7, "method": "not_a_real_method"})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == -32601
