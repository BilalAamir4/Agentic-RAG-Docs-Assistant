"""Tests for the FastAPI health endpoint."""

from fastapi.testclient import TestClient

from ragdocs.api.app import app

client = TestClient(app)


def test_api_health_endpoint() -> None:
    """Ensure /api/health returns 200 with required environment and status keys."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"status", "env", "python", "commit"}
    assert data["status"] == "ok"
    assert isinstance(data["env"], str)
    assert isinstance(data["python"], str)
    assert isinstance(data["commit"], str)
