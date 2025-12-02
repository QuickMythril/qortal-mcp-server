from fastapi.testclient import TestClient

from qortal_mcp.server import app


client = TestClient(app)


def test_mcp_call_tool_validate_address():
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "call_tool",
        "params": {"tool": "validate_address", "params": {"address": "QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV"}},
    }
    resp = client.post("/mcp", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "1"
    result = body["result"]
    assert "content" in result
    assert "structuredContent" in result
    assert result["structuredContent"]["isValid"] is True


def test_mcp_initialize():
    payload = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26"},
    }
    resp = client.post("/mcp", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "init-1"
    result = body["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert "serverInfo" in result
    assert "capabilities" in result
