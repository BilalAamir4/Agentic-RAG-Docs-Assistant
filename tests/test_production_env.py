"""The production environment variable table from docs/progress/M14-production-deploy.md.

Builds Settings from exactly that table (fake values, no .env, nothing else in the
environment) and checks the startup validation accepts it.
"""

from pathlib import Path

import pytest

from ragdocs.api.startup import validate_runtime_settings
from ragdocs.config import Settings

# Variables Bilal sets, and the two the Upstash integration injects (integration names).
PRODUCTION_ENV = {
    "GROQ_API_KEY": "fake-groq-key",
    "GOOGLE_API_KEY": "fake-google-key",
    "TAVILY_API_KEY": "fake-tavily-key",
    "RAGDOCS_ENV": "production",
    "LANGSMITH_TRACING": "false",
    "IP_HASH_SALT": "0" * 64,
    "LLM_MAX_RETRIES": "1",
    "KV_REST_API_URL": "https://fake-upstash.example",
    "KV_REST_API_TOKEN": "fake-upstash-token",
}

# The setting name startup validation reports when a variable is removed.
REQUIRED_REPORTS = {
    "GROQ_API_KEY": "GROQ_API_KEY",
    "GOOGLE_API_KEY": "GOOGLE_API_KEY",
    "TAVILY_API_KEY": "TAVILY_API_KEY",
    "KV_REST_API_URL": "UPSTASH_REDIS_REST_URL",
    "KV_REST_API_TOKEN": "UPSTASH_REDIS_REST_TOKEN",
}

# Every other name Settings could read for these fields; cleared so the test is exact.
CLEARED = (
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "KV_REST_API_READ_ONLY_TOKEN",
    "COHERE_API_KEY",
    "LANGSMITH_API_KEY",
    "LANGSMITH_TRACING_SAMPLING_RATE",
    "RATE_LIMIT_PER_IP_PER_HOUR",
)


def _settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, drop: str | None = None) -> Settings:
    for name in CLEARED:
        monkeypatch.delenv(name, raising=False)
    for name, value in PRODUCTION_ENV.items():
        if name != drop:
            monkeypatch.setenv(name, value)
        else:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return Settings(_env_file=tmp_path / "no.env")


def test_production_table_passes_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The documented table starts the app: production, 1 retry, salt set, tracing off."""
    settings = _settings(monkeypatch, tmp_path)
    validate_runtime_settings(settings)
    assert settings.env == "production"
    assert settings.llm_max_retries == 1
    assert settings.ip_hash_salt is not None
    assert settings.ip_hash_salt.get_secret_value() == "0" * 64
    assert settings.langsmith_tracing is False
    assert settings.use_reranker is False


@pytest.mark.parametrize("variable", sorted(REQUIRED_REPORTS))
def test_removing_a_required_variable_fails_startup(
    variable: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Dropping any required variable raises RuntimeError naming that setting."""
    settings = _settings(monkeypatch, tmp_path, drop=variable)
    with pytest.raises(RuntimeError) as info:
        validate_runtime_settings(settings)
    assert REQUIRED_REPORTS[variable] in str(info.value)
