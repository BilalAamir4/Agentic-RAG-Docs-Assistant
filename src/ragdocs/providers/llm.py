"""LLM provider factories and callback utilities."""

from typing import Any, Literal
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from ragdocs.config import Settings, get_settings


class CallCounter(BaseCallbackHandler):
    """Callback handler tracking the total number of chat-model and LLM calls."""

    def __init__(self) -> None:
        super().__init__()
        self.llm_calls: int = 0
        self._counted_runs: set[UUID] = set()

    def _record_call(self, run_id: UUID) -> None:
        if run_id not in self._counted_runs:
            self._counted_runs.add(run_id)
            self.llm_calls += 1

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Increment count on chat model execution start."""
        self._record_call(run_id)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Increment count on base LLM execution start."""
        self._record_call(run_id)


def get_chat_model(
    role: Literal["generator", "grader", "judge"],
    settings: Settings | None = None,
) -> BaseChatModel:
    """Return a configured LangChain chat model at temperature 0 for the specified role.

    Args:
        role: Model role ('generator', 'grader', or 'judge').
        settings: Application settings instance; defaults to cached get_settings().

    Returns:
        A BaseChatModel instance configured for the given role.

    Raises:
        ValueError: If role is unrecognized or judge_model is unset when role='judge'.
    """
    settings = settings or get_settings()

    if role == "generator":
        model_name = settings.generator_model
        api_key = settings.require("groq_api_key")
        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=0,
            max_retries=3,
        )

    if role == "grader":
        model_name = settings.grader_model
        api_key = settings.require("groq_api_key")
        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=0,
            max_retries=3,
        )

    if role == "judge":
        if not settings.judge_model:
            raise ValueError("judge_model is unset in Settings.")
        # Lazy import because langchain_google_genai is offline/dev-only and not installed on Vercel
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = settings.require("google_api_key")
        return ChatGoogleGenerativeAI(
            model=settings.judge_model,
            google_api_key=api_key,
            temperature=0,
        )

    raise ValueError(f"Unknown role: {role!r}. Expected 'generator', 'grader', or 'judge'.")
