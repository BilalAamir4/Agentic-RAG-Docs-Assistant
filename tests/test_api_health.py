"""Tests for FastAPI health and dependency probe endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from ragdocs.api.app import app

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parent.parent


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


def test_api_deps_probe_endpoint() -> None:
    """Ensure /api/deps-probe returns 200 and lists every package from requirements.txt."""
    response = client.get("/api/deps-probe")
    assert response.status_code == 200
    data = response.json()
    assert "packages" in data
    assert "total_ms" in data
    assert isinstance(data["total_ms"], (int, float))

    # Read requirements.txt packages
    req_file = REPO_ROOT / "requirements.txt"
    expected_packages: list[str] = []
    with open(req_file, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            pkg = stripped.split("==")[0].split(">=")[0].split("<=")[0].strip()
            expected_packages.append(pkg)

    probed_names = [pkg_entry["name"] for pkg_entry in data["packages"]]
    for expected in expected_packages:
        assert expected in probed_names, f"Expected package '{expected}' missing from deps-probe"
