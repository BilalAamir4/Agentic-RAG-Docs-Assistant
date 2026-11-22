"""Tests for the Upstash environment variable aliases in Settings (M14)."""

from pathlib import Path

import pytest

from ragdocs.config import Settings

UPSTASH_NAMES = (
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "KV_REST_API_URL",
    "KV_REST_API_TOKEN",
    "KV_REST_API_READ_ONLY_TOKEN",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove every Upstash-related variable and run in an empty directory (no .env)."""
    for name in UPSTASH_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


def _build(tmp_path: Path) -> Settings:
    return Settings(_env_file=tmp_path / "missing.env")


def _values(settings: Settings) -> tuple[str | None, str | None]:
    url, token = settings.upstash_redis_rest_url, settings.upstash_redis_rest_token
    return (
        url.get_secret_value() if url else None,
        token.get_secret_value() if token else None,
    )


def test_upstash_names_set_both_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """UPSTASH_REDIS_REST_URL and _TOKEN alone set both fields."""
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://fake-upstash.example")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "fake-upstash-token")
    assert _values(_build(tmp_path)) == ("https://fake-upstash.example", "fake-upstash-token")


def test_integration_names_set_both_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """KV_REST_API_URL and KV_REST_API_TOKEN alone set both fields."""
    monkeypatch.setenv("KV_REST_API_URL", "https://fake-kv.example")
    monkeypatch.setenv("KV_REST_API_TOKEN", "fake-kv-token")
    assert _values(_build(tmp_path)) == ("https://fake-kv.example", "fake-kv-token")


def test_upstash_names_win_over_integration_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With both pairs present the UPSTASH_ values are used."""
    monkeypatch.setenv("KV_REST_API_URL", "https://fake-kv.example")
    monkeypatch.setenv("KV_REST_API_TOKEN", "fake-kv-token")
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://fake-upstash.example")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "fake-upstash-token")
    assert _values(_build(tmp_path)) == ("https://fake-upstash.example", "fake-upstash-token")


def test_read_only_token_sets_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The read-only token is never accepted as the Upstash token."""
    monkeypatch.setenv("KV_REST_API_READ_ONLY_TOKEN", "fake-read-only-token")
    assert _values(_build(tmp_path)) == (None, None)


def test_field_names_still_work_as_arguments(tmp_path: Path) -> None:
    """Existing tests and code that pass the field names keep working."""
    settings = Settings(
        upstash_redis_rest_url="https://x.example",
        upstash_redis_rest_token="t",
        _env_file=tmp_path / "missing.env",
    )
    assert _values(settings) == ("https://x.example", "t")
