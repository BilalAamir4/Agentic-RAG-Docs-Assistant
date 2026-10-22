"""Gemini embeddings provider."""

from typing import Any

import numpy as np
from google import genai
from google.genai import errors, types
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ragdocs.config import Settings, get_settings

MAX_BATCH_SIZE = 100
MAX_BATCH_TOKENS = 20_000
TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_TYPE_QUERY = "RETRIEVAL_QUERY"


def _is_retryable_error(exc: BaseException) -> bool:
    """Return True if exception represents an HTTP 429 or 5xx error."""
    if isinstance(exc, errors.APIError):
        return exc.code == 429 or exc.code >= 500
    return False


def _on_retry_exhausted(retry_state: RetryCallState) -> Any:
    """Raise clear error after all retry attempts are exhausted."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    raise RuntimeError(
        f"Gemini embeddings API call failed after {retry_state.attempt_number} attempts: {exc}"
    ) from exc


def _normalize_l2(vectors: np.ndarray) -> np.ndarray:
    """Normalize vectors along the last axis to unit L2 norm."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (vectors / norms).astype(np.float32)


def _compute_backoff(retry_state: RetryCallState) -> float:
    """Calculate wait time with exponential backoff starting at 2s and RetryInfo delay."""
    base_wait = float(wait_exponential(multiplier=2, min=2, max=65)(retry_state))
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, errors.APIError) and exc.code == 429:
        delay_sec = 0.0
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            error_dict = details.get("error", {}) if "error" in details else details
            for item in error_dict.get("details", []):
                if isinstance(item, dict) and str(item.get("@type", "")).endswith("RetryInfo"):
                    delay_str = str(item.get("retryDelay", ""))
                    if delay_str.endswith("s"):
                        try:
                            delay_sec = float(delay_str[:-1])
                        except ValueError:
                            pass
        if delay_sec == 0.0 and retry_state.attempt_number >= 3:
            delay_sec = 35.0
        return max(base_wait, delay_sec)
    return base_wait


class GeminiEmbedder:
    """Embedder using Google Gemini embeddings API with batching, retries, and L2 normalization."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        api_key = self.settings.require("google_api_key")
        self.client = genai.Client(api_key=api_key)
        self.model = self.settings.embedding_model or "gemini-embedding-001"
        self.dim = self.settings.embedding_dim
        self.api_calls: int = 0

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=_compute_backoff,
        stop=stop_after_attempt(6),
        retry_error_callback=_on_retry_exhausted,
    )
    def _call_embed_content(
        self,
        contents: str | list[str],
        task_type: str,
    ) -> list[list[float]]:
        """Call the Gemini API with tenacity retry logic."""
        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=self.dim,
        )
        self.api_calls += 1
        response = self.client.models.embed_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        if not response.embeddings:
            return []
        return [emb.values for emb in response.embeddings]

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query string into an L2-normalised float32 vector."""
        res = self._call_embed_content(text, TASK_TYPE_QUERY)
        if not res or not res[0]:
            return np.zeros((self.dim,), dtype=np.float32)
        vec = np.array(res[0], dtype=np.float32)
        return _normalize_l2(vec)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Embed a list of document texts in batches of up to 100 into L2-normalised vectors."""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        batches: list[list[str]] = []
        current_batch: list[str] = []
        current_tokens = 0
        for t in texts:
            est_tokens = max(1, len(t) // 4)
            if current_batch and (
                len(current_batch) >= MAX_BATCH_SIZE
                or current_tokens + est_tokens > MAX_BATCH_TOKENS
            ):
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            current_batch.append(t)
            current_tokens += est_tokens

        if current_batch:
            batches.append(current_batch)

        all_vectors: list[list[float]] = []
        for batch in batches:
            batch_vectors = self._call_embed_content(batch, TASK_TYPE_DOCUMENT)
            all_vectors.extend(batch_vectors)

        arr = np.array(all_vectors, dtype=np.float32)
        return _normalize_l2(arr)
