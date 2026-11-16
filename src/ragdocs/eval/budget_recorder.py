"""Record every live Groq and Gemini call of this process in cache/budget.json (D7).

install_budget_recorder() registers one BudgetRecorder through a LangChain configure
hook, so every chat-model call in the process reports to it without passing callbacks,
and as a usage listener for Gemini embedding calls (ragdocs.providers.usage). Each call
is written to the BudgetStore as it finishes: successful calls with their reported
tokens, failed calls as one request with zero tokens. Offline only.
"""

from contextvars import ContextVar
from typing import Any

from langchain_core.tracers.context import register_configure_hook

from ragdocs.config import Settings, get_settings
from ragdocs.eval.throttle import BudgetStore, default_store
from ragdocs.providers.usage import (
    TokenUsage,
    add_usage_listener,
    remove_usage_listener,
)


class BudgetRecorder(TokenUsage):
    """TokenUsage that also appends each call to a BudgetStore."""

    def __init__(self, store: BudgetStore) -> None:
        super().__init__()
        self.store = store

    def _add_call(self, model: str, tokens: tuple[int, int] | None) -> None:
        """Count the call and persist it (one request; its tokens or 0)."""
        super()._add_call(model, tokens)
        self.store.add(model, 1, sum(tokens) if tokens else 0)

    def on_usage(self, model: str, requests: int, tokens: int) -> None:
        """Usage listener for calls outside LangChain (Gemini embeddings)."""
        self.store.add(model, requests, tokens)


_ACTIVE: ContextVar[Any] = ContextVar("ragdocs_budget_recorder", default=None)
_hook_registered = False


def install_budget_recorder(
    settings: Settings | None = None, store: BudgetStore | None = None
) -> BudgetRecorder:
    """Start recording every live call of this process; return the recorder.

    Calling it again replaces the previous recorder.
    """
    global _hook_registered
    if not _hook_registered:
        register_configure_hook(_ACTIVE, True)
        _hook_registered = True
    uninstall_budget_recorder()
    recorder = BudgetRecorder(store or default_store(settings or get_settings()))
    _ACTIVE.set(recorder)
    add_usage_listener(recorder.on_usage)
    return recorder


def uninstall_budget_recorder() -> None:
    """Stop recording (used by tests)."""
    current = _ACTIVE.get()
    if current is not None:
        remove_usage_listener(current.on_usage)
    _ACTIVE.set(None)


def recorder_active() -> bool:
    """True when a BudgetRecorder is installed in this context."""
    return _ACTIVE.get() is not None
