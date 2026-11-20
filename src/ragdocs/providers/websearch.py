"""Tavily web search restricted to the docs domain (M10, D8). Runtime-safe.

Verified against tavily-python 0.8.5 (.venv/Lib/site-packages/tavily):
- TavilyClient(api_key=...) (tavily.py line 44). With no key it runs in keyless mode
  (line 74), so TavilySearch refuses to start without TAVILY_API_KEY.
- search(query, search_depth=..., max_results=..., include_domains=[...], ...) returns
  a dict whose "results" items carry url, title, content, score (and raw_content,
  favicon when requested). include_domains_mode defaults to "restrict" server side
  (https://docs.tavily.com/documentation/api-reference/endpoint/search).
- Errors (_handle_error_response, line 116): 429 UsageLimitExceededError; 401
  InvalidAPIKeyError; 403, 432, 433 ForbiddenError (tavily.errors); 400
  BadRequestError; any other status requests.HTTPError (an OSError subclass, with
  .response.status_code); a request timeout raises tavily.errors.TimeoutError.
- A connection error is not caught by tavily: requests.exceptions.ConnectionError (an
  OSError with no response) reaches the caller (tavily.py line 238 only catches
  requests.exceptions.Timeout). M11 S1 retries it and timeouts like 429 and 5xx.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

import requests
from tavily import BadRequestError, InvalidAPIKeyError, TavilyClient, UsageLimitExceededError
from tavily.errors import ForbiddenError
from tavily.errors import TimeoutError as TavilyTimeoutError

from ragdocs.config import Settings
from ragdocs.docs_urls import is_docs_host
from ragdocs.schemas import WebResult, WebSearchOutcome

logger = logging.getLogger(__name__)

SEARCH_DEPTH = "basic"
KEY_ENV_VAR = "TAVILY_API_KEY"


class WebSearchError(RuntimeError):
    """Tavily search failed. Never contains the key.

    kind (M11 S1, read by ragdocs.providers.errors.error_kind): "transient" for
    connection errors, timeouts and 429/5xx after the retries; "permanent" for
    plan-limit (403/432/433), 400, auth and other HTTP statuses; "unclassified" else.
    """

    def __init__(self, message: str, kind: str = "unclassified") -> None:
        """Store the message and the error kind."""
        super().__init__(message)
        self.kind = kind


class WebSearchAuthError(WebSearchError):
    """Tavily rejected the API key."""

    def __init__(self, message: str) -> None:
        """Auth errors are always permanent."""
        super().__init__(message, kind="permanent")


def _default_client(api_key: str) -> Any:
    """Real Tavily client."""
    return TavilyClient(api_key=api_key)


def _status(exc: Exception) -> int | None:
    """HTTP status of a Tavily or requests error, when known."""
    if isinstance(exc, UsageLimitExceededError):
        return 429
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _is_connection_or_timeout(exc: Exception) -> bool:
    """requests connection errors and timeouts, and tavily's TimeoutError (no HTTP status)."""
    return isinstance(
        exc, TavilyTimeoutError | requests.exceptions.ConnectionError | requests.exceptions.Timeout
    )


def _retryable(exc: Exception) -> bool:
    """429, 5xx, connection errors and timeouts are retried."""
    if _is_connection_or_timeout(exc):
        return True
    status = _status(exc)
    return status is not None and (status == 429 or 500 <= status < 600)


class TavilySearch:
    """Docs-domain web search with retries and a defensive host filter."""

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[str], Any] = _default_client,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Build the client; raise RuntimeError naming TAVILY_API_KEY when it is missing."""
        self.settings = settings
        self.domain = settings.docs_domain
        self._sleep = sleep
        self._client = client_factory(settings.require(KEY_ENV_VAR))

    def _request_kwargs(self) -> dict[str, Any]:
        """Parameters sent with every search (names verified in tavily-python 0.8.5)."""
        return {
            "include_domains": [self.domain],
            "max_results": self.settings.web_max_results,
            "search_depth": SEARCH_DEPTH,
        }

    def _call(self, query: str) -> dict[str, Any]:
        """One search with retries on 429, 5xx, connection errors and timeouts.

        Settings.web_search_max_attempts attempts in total, backoff starting at
        Settings.web_search_backoff_s and doubling (1 s, 2 s, ...).
        """
        attempts = self.settings.web_search_max_attempts
        delay = self.settings.web_search_backoff_s
        for attempt in range(1, attempts + 1):
            try:
                return self._client.search(query, **self._request_kwargs())
            except InvalidAPIKeyError:
                raise WebSearchAuthError(
                    f"Tavily rejected the API key (401); check {KEY_ENV_VAR} in .env"
                ) from None
            except ForbiddenError:
                raise WebSearchError(
                    f"Tavily refused the request (403/432/433: forbidden or plan limit); "
                    f"check {KEY_ENV_VAR} and its plan",
                    kind="permanent",
                ) from None
            except BadRequestError as exc:
                raise WebSearchError(
                    f"Tavily search failed: {type(exc).__name__}", kind="permanent"
                ) from None
            except (UsageLimitExceededError, TavilyTimeoutError, OSError) as exc:
                self._raise_unless_retry(exc, attempt, attempts)
                logger.warning(
                    "Tavily %s (status %s), retry %d in %.1f s",
                    type(exc).__name__,
                    _status(exc),
                    attempt,
                    delay,
                )
                self._sleep(delay)
                delay *= 2
        raise WebSearchError("Tavily search made no attempt")  # attempts < 1

    @staticmethod
    def _raise_unless_retry(exc: Exception, attempt: int, attempts: int) -> None:
        """Raise WebSearchError when exc is not retryable or this was the last attempt."""
        status = _status(exc)
        retryable = _retryable(exc)
        if retryable and attempt < attempts:
            return
        if retryable:
            kind = "transient"
        elif status is not None:
            kind = "permanent"
        else:
            kind = "unclassified"
        raise WebSearchError(
            f"Tavily search failed after {attempt} attempt(s): "
            f"{type(exc).__name__} (status {status})",
            kind=kind,
        ) from None

    def search_with_diagnostics(self, query: str) -> WebSearchOutcome:
        """Search and drop results whose host is not docs_domain or a subdomain of it."""
        raw = self._call(query).get("results") or []
        kept: list[WebResult] = []
        dropped: list[str] = []
        for r in raw:
            url = str(r.get("url") or "")
            if not is_docs_host(url, self.domain):
                dropped.append(url)
                continue
            kept.append(
                WebResult(
                    url=url, title=str(r.get("title") or ""), content=str(r.get("content") or "")
                )
            )
        if dropped:
            logger.warning("Dropped %d off-domain web result(s): %s", len(dropped), dropped)
        return WebSearchOutcome(
            query=query,
            results=kept,
            raw_urls=[str(r.get("url") or "") for r in raw],
            dropped_off_domain=dropped,
        )

    def search(self, query: str) -> list[dict[str, str]]:
        """Return docs-domain results as dicts with exactly url, title, content."""
        return [r.model_dump() for r in self.search_with_diagnostics(query).results]
