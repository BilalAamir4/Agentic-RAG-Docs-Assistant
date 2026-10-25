"""Base pipeline interface, execution runner, and trace protocols."""

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from ragdocs.schemas import PipelineResult, TraceEvent


def safe_error_message(exc: BaseException) -> str:
    """Format an exception into a safe message without secrets or stack trace."""
    msg = str(exc)
    try:
        from ragdocs.config import get_settings

        settings = get_settings()
        for attr in (
            "groq_api_key",
            "google_api_key",
            "cohere_api_key",
            "tavily_api_key",
            "upstash_redis_rest_token",
        ):
            secret = getattr(settings, attr, None)
            if secret and secret.get_secret_value():
                msg = msg.replace(secret.get_secret_value(), "[REDACTED]")
    except Exception:
        pass

    # Keep only the first line to guarantee no stack trace leaks
    first_line = msg.splitlines()[0] if msg else ""
    return f"{type(exc).__name__}: {first_line}".strip()


@runtime_checkable
class Pipeline(Protocol):
    """Protocol for RAG pipelines supporting streaming execution traces."""

    name: str

    def stream(self, question: str) -> Iterator[TraceEvent]:
        """Execute pipeline and stream TraceEvent instances.

        The final event must have type='answer' and data=PipelineResult.model_dump().
        On any exception, yields one type='error' event with a safe message and stops.
        """
        ...


def run(pipeline: Pipeline, question: str) -> PipelineResult:
    """Consume pipeline stream and return the parsed final PipelineResult.

    Args:
        pipeline: The pipeline instance to run.
        question: User query string.

    Returns:
        The parsed PipelineResult from the final 'answer' event.

    Raises:
        RuntimeError: If pipeline yields an error event or terminates without an answer event.
    """
    final_event: TraceEvent | None = None
    for event in pipeline.stream(question):
        final_event = event

    if final_event is None:
        raise RuntimeError(f"Pipeline '{pipeline.name}' produced no events.")

    if final_event.type == "error":
        raise RuntimeError(f"Pipeline '{pipeline.name}' failed: {final_event.message}")

    if final_event.type != "answer":
        raise RuntimeError(
            f"Pipeline '{pipeline.name}' terminated with unexpected event type '{final_event.type}'"
        )

    return PipelineResult.model_validate(final_event.data)
