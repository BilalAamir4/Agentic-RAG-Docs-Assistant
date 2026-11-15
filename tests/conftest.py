"""Shared pytest fixtures.

Every test not marked live runs with LangSmith tracing forced off. Real environment
variables override .env in pydantic-settings, so this holds even when .env enables
tracing. Names verified in langsmith 0.14.7 (langsmith/utils.py get_env_var and
tracing_is_enabled): LANGSMITH_* is read before LANGCHAIN_*, and TRACING_V2 before
TRACING.
"""

import os
from collections.abc import Iterator

import pytest
from langsmith import utils as ls_utils

from ragdocs.config import get_settings

TRACING_FLAGS = ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2")
API_KEYS = ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")


def _clear_caches() -> None:
    """Clear cached settings and langsmith's cached env var lookups."""
    get_settings.cache_clear()
    ls_utils.get_env_var.cache_clear()
    ls_utils.get_tracer_project.cache_clear()


@pytest.fixture(autouse=True)
def tracing_off(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force tracing off and remove LangSmith keys for every non-live test."""
    if request.node.get_closest_marker("live"):
        yield
        return
    saved = {k: v for k, v in os.environ.items() if k.startswith(("LANGSMITH_", "LANGCHAIN_"))}
    for name in TRACING_FLAGS:
        monkeypatch.setenv(name, "false")
    for name in API_KEYS:
        monkeypatch.delenv(name, raising=False)
    _clear_caches()
    yield
    # configure_tracing writes os.environ directly; drop anything it added.
    for key in [k for k in os.environ if k.startswith(("LANGSMITH_", "LANGCHAIN_"))]:
        if key not in saved:
            del os.environ[key]
    _clear_caches()
