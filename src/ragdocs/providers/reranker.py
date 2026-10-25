"""Cohere and no-op document reranker providers."""

from typing import Protocol, runtime_checkable

from cohere import ClientV2
from cohere.core.api_error import ApiError
from cohere.errors import TooManyRequestsError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ragdocs.config import Settings, get_settings


@runtime_checkable
class Reranker(Protocol):
    """Protocol defining the interface for document rerankers."""

    def rerank(self, query: str, texts: list[str], top_n: int) -> list[tuple[int, float]]:
        """Rerank candidate texts against query.

        Args:
            query: The search query string.
            texts: List of candidate document texts.
            top_n: Maximum number of results to return.

        Returns:
            List of (input_index, relevance_score) tuples ordered best first.
        """
        ...


class NoopReranker:
    """No-op reranker returning candidates in original order with 0.0 scores."""

    def rerank(self, query: str, texts: list[str], top_n: int) -> list[tuple[int, float]]:
        """Return the first top_n texts in original order with score 0.0."""
        if not texts or top_n <= 0:
            return []
        n = min(top_n, len(texts))
        return [(i, 0.0) for i in range(n)]


def _is_retryable_error(exc: BaseException) -> bool:
    """Return True if exception represents an HTTP 429 or 5xx error."""
    if isinstance(exc, TooManyRequestsError):
        return True
    if isinstance(exc, ApiError):
        status = getattr(exc, "status_code", None)
        return status == 429 or (status is not None and status >= 500)
    return False


class CohereReranker:
    """Reranker using Cohere ClientV2 with retry backoff and rate-limit handling."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        api_key = self.settings.require("cohere_api_key")
        self.client = ClientV2(api_key=api_key)
        self.model = self.settings.rerank_model or "rerank-v3.5"
        self.api_calls: int = 0

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def _call_rerank(self, query: str, texts: list[str], top_n: int) -> list[tuple[int, float]]:
        """Execute rerank API call with exponential backoff on 429/5xx errors."""
        self.api_calls += 1
        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=texts,
            top_n=top_n,
        )
        if not response.results:
            return []
        return [(item.index, float(item.relevance_score)) for item in response.results]

    def rerank(self, query: str, texts: list[str], top_n: int) -> list[tuple[int, float]]:
        """Rerank candidate texts against query using Cohere ClientV2.

        Args:
            query: The search query string.
            texts: List of candidate document texts.
            top_n: Maximum number of results to return.

        Returns:
            List of (input_index, relevance_score) tuples ordered best first.
        """
        if not texts or top_n <= 0:
            return []
        top_n_clamped = min(top_n, len(texts))
        return self._call_rerank(query=query, texts=texts, top_n=top_n_clamped)


def get_reranker(settings: Settings | None = None) -> Reranker:
    """Return configured reranker instance, defaulting to Noop when disabled."""
    settings = settings or get_settings()
    if not settings.use_reranker:
        return NoopReranker()
    return CohereReranker(settings=settings)
