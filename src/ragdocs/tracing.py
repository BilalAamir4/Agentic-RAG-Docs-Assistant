"""LangSmith tracing helpers that are safe to import at runtime.

Verified against langsmith 0.14.7 and langchain-core 1.6.10 (see
docs/progress/M07-langsmith-tracing.md):
- langsmith.utils.get_env_var reads LANGSMITH_<NAME> then LANGCHAIN_<NAME> and is
  lru_cached, so caches are cleared after env vars change.
- langsmith.utils.tracing_is_enabled checks TRACING_V2 before TRACING.
- langsmith.run_helpers.trace opens a run; LangChain runs started inside it nest as
  children because langchain-core reads the same tracing context.

Imports only the standard library, langsmith, langchain-core and ragdocs.config.
"""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import run_helpers
from langsmith import utils as ls_utils

from ragdocs.config import Settings

logger = logging.getLogger(__name__)

ENV_TRACING = "LANGSMITH_TRACING"
# Checked before LANGSMITH_TRACING by langsmith.utils.tracing_is_enabled.
ENV_TRACING_V2 = "LANGSMITH_TRACING_V2"
ENV_API_KEY = "LANGSMITH_API_KEY"
ENV_PROJECT = "LANGSMITH_PROJECT"
ENV_ENDPOINT = "LANGSMITH_ENDPOINT"
ENV_SAMPLING_RATE = "LANGSMITH_TRACING_SAMPLING_RATE"

_last_root_run: Any = None


def _clear_env_caches() -> None:
    """Clear langsmith's cached env var lookups so new values take effect."""
    ls_utils.get_env_var.cache_clear()
    ls_utils.get_tracer_project.cache_clear()


def configure_tracing(settings: Settings) -> bool:
    """Export LangSmith env vars from settings and return whether tracing is active.

    Values already present in the real environment win (os.environ.setdefault).
    The API key is never logged or printed.
    """
    if not settings.langsmith_tracing:
        os.environ[ENV_TRACING] = "false"
        os.environ[ENV_TRACING_V2] = "false"
        _clear_env_caches()
        return False

    key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else ""
    if not key:
        logger.warning(
            "LangSmith tracing requested but %s is not set; tracing is off.", ENV_API_KEY
        )
        _clear_env_caches()
        return False

    os.environ.setdefault(ENV_TRACING, "true")
    os.environ.setdefault(ENV_API_KEY, key)
    os.environ.setdefault(ENV_PROJECT, settings.langsmith_project)
    os.environ.setdefault(ENV_SAMPLING_RATE, str(settings.langsmith_sampling_rate))
    if settings.langsmith_endpoint:
        os.environ.setdefault(ENV_ENDPOINT, settings.langsmith_endpoint)
    _clear_env_caches()
    return True


def tracing_enabled() -> bool:
    """Return True when langsmith would record runs in the current context."""
    return bool(ls_utils.tracing_is_enabled())


class TracedRun:
    """Handle yielded by traced_run; a no-op when tracing is disabled."""

    def __init__(self, run_tree: Any = None) -> None:
        self._run_tree = run_tree
        self.run_id: str | None = str(run_tree.id) if run_tree is not None else None

    def set_outputs(self, outputs: dict[str, Any]) -> None:
        """Record outputs on the run."""
        if self._run_tree is not None:
            self._run_tree.end(outputs=outputs)

    def set_error(self, message: str) -> None:
        """Mark the run as failed with a safe message."""
        if self._run_tree is not None:
            self._run_tree.end(error=message)


@contextmanager
def traced_run(
    name: str,
    run_type: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Iterator[TracedRun]:
    """Open a LangSmith run around a block; LangChain runs inside it nest as children.

    When tracing is disabled no LangSmith client is constructed and no network call
    is made.
    """
    global _last_root_run
    if not tracing_enabled():
        yield TracedRun()
        return
    with run_helpers.trace(
        name, run_type=run_type, inputs=inputs, metadata=metadata, tags=tags
    ) as run_tree:
        if run_tree.parent_run_id is None:
            _last_root_run = run_tree
        yield TracedRun(run_tree)


def last_trace_url() -> str | None:
    """Return the LangSmith URL of the most recent root run, or None."""
    if _last_root_run is None:
        return None
    return str(_last_root_run.get_url())


def flush_traces() -> None:
    """Block until queued traces are sent; does nothing when tracing is disabled."""
    if tracing_enabled():
        wait_for_all_tracers()
