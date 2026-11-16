"""Token usage callback handler, safe to import at runtime.

Source verified for M08 (see docs/progress/M08-eval-harness.md, Step 1b):
- langchain-groq 1.1.3 `ChatGroq._create_chat_result` sets `AIMessage.usage_metadata`
  from the Groq `usage` field and puts `token_usage` and `model_name` in `llm_output`.
- langchain-google-genai 4.4.1 `_response_to_result` sets `AIMessage.usage_metadata`
  from the Gemini `usage_metadata` field.
- langchain-core 1.6.10 merges `llm_output` into `response_metadata` for single
  generations, passes the `LLMResult` to `on_llm_end`, and adds `ls_model_name` to the
  metadata given to `on_chat_model_start`.
- `with_structured_output` wraps the chat model in a RunnableSequence; callbacks reach
  the inner chat model, so `on_llm_end` still receives the raw AIMessage.
"""

import threading
from collections.abc import Callable
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from ragdocs.schemas import ModelTokenUsage, TokenUsageRecord

UNKNOWN_MODEL = "unknown"


def _usage_from_message(message: Any) -> tuple[int, int] | None:
    """Return (input, output) tokens from AIMessage.usage_metadata, or None."""
    if not isinstance(message, AIMessage) or not message.usage_metadata:
        return None
    meta = message.usage_metadata
    return int(meta.get("input_tokens") or 0), int(meta.get("output_tokens") or 0)


def _usage_from_llm_output(llm_output: dict[str, Any] | None) -> tuple[int, int] | None:
    """Return (prompt, completion) tokens from an OpenAI-style llm_output, or None."""
    token_usage = (llm_output or {}).get("token_usage")
    if not token_usage:
        return None
    return int(token_usage.get("prompt_tokens") or 0), int(
        token_usage.get("completion_tokens") or 0
    )


class TokenUsage(BaseCallbackHandler):
    """Record input and output tokens per model name over any number of LLM calls.

    The model name is the `ls_model_name` seen at call start (the configured model
    ID), falling back to the response's `model_name`. Calls whose response carries no
    usage data are counted in `usage_missing`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._run_models: dict[UUID, str] = {}
        self._by_model: dict[str, ModelTokenUsage] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Remember the configured model name for this run."""
        name = (metadata or {}).get("ls_model_name")
        if name:
            with self._lock:
                self._run_models[run_id] = str(name)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        """Add the call's token usage to its model's totals."""
        message = None
        try:
            generation = response.generations[0][0]
            if isinstance(generation, ChatGeneration):
                message = generation.message
        except IndexError:
            pass
        tokens = _usage_from_message(message) or _usage_from_llm_output(response.llm_output)
        with self._lock:
            model = self._run_models.pop(run_id, None) or self._response_model(message, response)
        self._add_call(model, tokens)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        """Count a failed call (it still used a request) as a call without usage data."""
        with self._lock:
            model = self._run_models.pop(run_id, None) or UNKNOWN_MODEL
        self._add_call(model, None)

    def _add_call(self, model: str, tokens: tuple[int, int] | None) -> None:
        """Add one call for model; tokens is (input, output) or None when unreported."""
        with self._lock:
            entry = self._by_model.setdefault(model, ModelTokenUsage())
            entry.calls += 1
            if tokens is None:
                entry.usage_missing += 1
            else:
                entry.input_tokens += tokens[0]
                entry.output_tokens += tokens[1]

    @staticmethod
    def _response_model(message: Any, response: LLMResult) -> str:
        """Return the model name reported in the response, or UNKNOWN_MODEL."""
        if isinstance(message, AIMessage) and message.response_metadata.get("model_name"):
            return str(message.response_metadata["model_name"])
        name = (response.llm_output or {}).get("model_name")
        return str(name) if name else UNKNOWN_MODEL

    def record(self) -> TokenUsageRecord:
        """Return a snapshot of the totals and per-model breakdown."""
        with self._lock:
            by_model = {k: v.model_copy() for k, v in sorted(self._by_model.items())}
        return TokenUsageRecord(
            tokens_in=sum(v.input_tokens for v in by_model.values()),
            tokens_out=sum(v.output_tokens for v in by_model.values()),
            usage_missing=sum(v.usage_missing for v in by_model.values()),
            by_model=by_model,
        )


# Usage listeners for calls that LangChain callbacks do not see (Gemini embeddings).
# Offline tools register one (ragdocs.eval.budget_recorder); at runtime the list is
# empty and notify_usage does nothing.
UsageListener = Callable[[str, int, int], None]
_LISTENERS: list[UsageListener] = []


def add_usage_listener(listener: UsageListener) -> None:
    """Register listener(model, requests, tokens), called on every notify_usage."""
    if listener not in _LISTENERS:
        _LISTENERS.append(listener)


def remove_usage_listener(listener: UsageListener) -> None:
    """Unregister a listener added with add_usage_listener."""
    if listener in _LISTENERS:
        _LISTENERS.remove(listener)


def notify_usage(model: str, requests: int, tokens: int) -> None:
    """Report one API attempt's usage to every registered listener."""
    for listener in list(_LISTENERS):
        listener(model, requests, tokens)
