from fastapi.testclient import TestClient

from qortal_mcp.server import app


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
    assert resp.headers.get("X-Request-ID")


def test_metrics_endpoint_counts_requests():
    client = TestClient(app)
    client.get("/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    # Two requests so far: /health and /metrics
    assert data.get("requests", 0) >= 2
