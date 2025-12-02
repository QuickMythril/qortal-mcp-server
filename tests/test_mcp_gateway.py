from fastapi.testclient import TestClient

from qortal_mcp.server import app


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
