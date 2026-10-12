"""Tests for configuration settings and path resolution."""

from pathlib import Path

import pytest

from ragdocs.config import Settings


def test_settings_defaults_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings loads default values when no environment variables or .env file exist."""
    env_keys = [
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
        "COHERE_API_KEY",
        "TAVILY_API_KEY",
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "RAGDOCS_ENV",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.chdir(tmp_path)
    empty_env = tmp_path / ".env"
    settings = Settings(_env_file=empty_env)

    assert settings.env == "local"
    assert settings.groq_api_key is None
    assert settings.google_api_key is None
    assert settings.embedding_dim == 768
    assert settings.dense_k == 20
    assert settings.bm25_k == 20
    assert settings.rrf_k == 60
    assert settings.fused_k == 20
    assert settings.rerank_top_n == 5
    assert settings.final_k == 5
    assert settings.max_question_chars == 500
    assert settings.rate_limit_per_ip_per_hour == 20
    assert settings.daily_global_cap == 300
    assert settings.max_query_rewrites == 1
    assert settings.max_regenerations == 1
    assert settings.docs_domain == ""


def test_settings_require_raises_on_missing_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """require() raises RuntimeError naming the missing environment variable."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    empty_env = tmp_path / ".env"
    settings = Settings(_env_file=empty_env)

    with pytest.raises(RuntimeError) as exc_info:
        settings.require("GROQ_API_KEY")

    assert "GROQ_API_KEY" in str(exc_info.value)


def test_settings_require_returns_plain_value(tmp_path: Path) -> None:
    """require() returns plain string value for present secrets."""
    empty_env = tmp_path / ".env"
    settings = Settings(groq_api_key="gsk-secret-key-12345", _env_file=empty_env)

    assert settings.require("groq_api_key") == "gsk-secret-key-12345"
    assert settings.require("GROQ_API_KEY") == "gsk-secret-key-12345"


def test_repo_root_path_resolution_independent_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repo-root path resolution must not depend on the current working directory."""
    orig_settings = Settings()
    orig_index_dir = orig_settings.index_dir

    monkeypatch.chdir(tmp_path)
    new_settings = Settings()

    assert new_settings.index_dir == orig_index_dir
    assert new_settings.index_dir.is_absolute()
    assert new_settings.index_dir.as_posix().endswith("data/index")
    assert new_settings.data_dir.as_posix().endswith("data")
    assert new_settings.eval_path.as_posix().endswith("data/eval/eval_set.jsonl")
    assert new_settings.results_dir.as_posix().endswith("results")
    assert new_settings.cache_dir.as_posix().endswith("cache")
