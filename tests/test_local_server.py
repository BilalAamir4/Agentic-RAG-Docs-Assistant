"""Tests for ragdocs.api.local: the CSP header and the fake rate-limit flag (M13)."""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ragdocs.api.local import CSP, FAKE_LIMIT_ENV, app, apply_fake_limit, parse_fake_limit

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)
BODY = {"question": "How do I set a recursion limit?", "pipeline": "baseline"}


@pytest.fixture
def clean_overrides() -> Iterator[None]:
    """Remove any dependency override a test added to the shared local app."""
    yield
    app.dependency_overrides.clear()


def test_csp_constant_is_the_m14_policy() -> None:
    assert CSP == EXPECTED_CSP


def test_csp_header_on_page_and_api() -> None:
    client = TestClient(app)
    assert client.get("/").headers["content-security-policy"] == EXPECTED_CSP
    assert client.get("/api/health").headers["content-security-policy"] == EXPECTED_CSP


@pytest.mark.usefixtures("clean_overrides")
def test_fake_ip_limit_gives_429_with_retry_after() -> None:
    apply_fake_limit(app, parse_fake_limit("ip"))
    r = TestClient(app).post("/api/ask", json=BODY)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "5"
    assert r.json() == {"error": "Rate limit reached. Try again later.", "retry_after_s": 5}


@pytest.mark.usefixtures("clean_overrides")
def test_fake_global_limit_gives_503() -> None:
    apply_fake_limit(app, parse_fake_limit("global"))
    r = TestClient(app).post("/api/ask", json=BODY)
    assert r.status_code == 503
    assert r.json() == {"error": "The demo's daily budget is used up. It resets at 00:00 UTC."}


@pytest.mark.parametrize("value", [None, ""])
def test_unset_or_empty_flag_overrides_nothing(value: str | None) -> None:
    assert parse_fake_limit(value) is None


def test_unknown_flag_value_raises_naming_the_variable() -> None:
    with pytest.raises(ValueError, match=FAKE_LIMIT_ENV):
        parse_fake_limit("always")


def _import_local(value: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, FAKE_LIMIT_ENV: value}
    return subprocess.run(
        [sys.executable, "-c", "import ragdocs.api.local"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_importing_local_with_unknown_value_fails() -> None:
    result = _import_local("always")
    assert result.returncode != 0
    assert FAKE_LIMIT_ENV in result.stderr


def test_importing_local_with_known_value_succeeds() -> None:
    assert _import_local("ip").returncode == 0
