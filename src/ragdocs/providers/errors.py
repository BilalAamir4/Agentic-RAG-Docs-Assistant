"""Classify provider and parsing exceptions into error kinds (M11 S1). Runtime-safe.

Imports only the standard library, pydantic, langchain-core and the provider packages.

Verified against the installed packages (docs/progress/M11-self-rag.md, Step 1):
- groq 0.37.1: every HTTP 400 raises groq.BadRequestError (status_code 400); exc.body is
  the decoded JSON response. A structured call with method="json_schema", strict=True
  that the model cannot satisfy returns {"error": {"type": "invalid_request_error",
  "code": "json_validate_failed", ...}} (q049 in M10). 429 is groq.RateLimitError;
  transport failures are groq.APIConnectionError (APITimeoutError subclasses it); 5xx
  is groq.InternalServerError; 401 AuthenticationError; 403 PermissionDeniedError.
- langchain-core 1.6.10: PydanticOutputParser raises OutputParserException for invalid
  JSON and for JSON that fails schema validation (it wraps pydantic.ValidationError).
  pydantic.ValidationError is also accepted, for validation done after parsing.

Kinds:
- "structured_output": the model's structured output was unusable (the three cases above).
- "rate_limit": a provider rate limit (429) that survived the client's retries.
- "transient": connection errors, timeouts, 5xx; may succeed on a later attempt.
- "permanent": auth, permission, plan-limit and other request errors.
- "unclassified": anything else.

Stored failed attempts carry only a message, so classify_message gives the same kinds
from a message: "<ClassName>" (agentic error events) or "<ClassName>: <text>" (baseline,
ragdocs.pipelines.base.safe_error_message). A name that does not identify one kind on
its own (for example a bare "BadRequestError" or "WebSearchError") is "unclassified".
"""

from collections.abc import Sequence
from typing import Any, Literal

import groq
import pydantic
from langchain_core.exceptions import OutputParserException

ErrorKind = Literal["structured_output", "rate_limit", "transient", "permanent", "unclassified"]
ERROR_KINDS: tuple[ErrorKind, ...] = (
    "structured_output",
    "rate_limit",
    "transient",
    "permanent",
    "unclassified",
)
JSON_VALIDATE_FAILED = "json_validate_failed"
RATE_LIMIT_NAMES: tuple[str, ...] = ("RateLimitError",)

# Class names that identify one kind from a stored message on their own.
STRUCTURED_NAMES = frozenset({"OutputParserException", "ValidationError"})
TRANSIENT_NAMES = frozenset({"APIConnectionError", "APITimeoutError", "InternalServerError"})
PERMANENT_NAMES = frozenset({"AuthenticationError", "PermissionDeniedError", "WebSearchAuthError"})


def groq_error_code(exc: BaseException) -> str | None:
    """The error.code field of a groq APIStatusError body, when present."""
    body: Any = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else None


def is_structured_output_error(exc: BaseException) -> bool:
    """True exactly for unusable structured output.

    That is: a groq 400 whose body code is json_validate_failed, an OutputParserException,
    or a pydantic ValidationError. False for everything else, including other 400s,
    429, 5xx, timeouts, connection and auth errors.
    """
    if isinstance(exc, OutputParserException | pydantic.ValidationError):
        return True
    return isinstance(exc, groq.BadRequestError) and groq_error_code(exc) == JSON_VALIDATE_FAILED


def _groq_kind(exc: groq.GroqError) -> ErrorKind:
    """Kind of a groq exception that is not a structured-output error."""
    if isinstance(exc, groq.RateLimitError):
        return "rate_limit"
    if isinstance(exc, groq.APIConnectionError | groq.InternalServerError):
        return "transient"
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status >= 500:
        return "transient"
    if isinstance(exc, groq.APIStatusError):
        return "permanent"
    return "unclassified"


def error_kind(exc: BaseException) -> ErrorKind:
    """Classify a live exception (see the module docstring for the kinds).

    Web search errors are classified by their own `kind` attribute when they carry one
    (ragdocs.providers.websearch.WebSearchError), so this module needs no import of it.
    """
    if is_structured_output_error(exc):
        return "structured_output"
    if isinstance(exc, groq.GroqError):
        return _groq_kind(exc)
    own = getattr(exc, "kind", None)
    if own in ERROR_KINDS:
        return own
    return "unclassified"


def classify_message(
    message: str, rate_limit_prefixes: Sequence[str] = RATE_LIMIT_NAMES
) -> ErrorKind:
    """Classify a stored failed-attempt message ("Name" or "Name: text")."""
    if any(message.startswith(p) for p in rate_limit_prefixes):
        return "rate_limit"
    name, _, text = message.partition(":")
    name = name.strip()
    if name in STRUCTURED_NAMES:
        return "structured_output"
    if name == "BadRequestError" and JSON_VALIDATE_FAILED in text:
        return "structured_output"
    if name in TRANSIENT_NAMES:
        return "transient"
    if name in PERMANENT_NAMES:
        return "permanent"
    return "unclassified"
