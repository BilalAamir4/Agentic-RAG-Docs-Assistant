"""Tests for ragdocs.providers.errors (M11 S1). Every exception is built directly; no network."""

import groq
import httpx
import pydantic
import pytest
from langchain_core.exceptions import OutputParserException

from ragdocs.providers.errors import (
    classify_message,
    error_kind,
    groq_error_code,
    is_structured_output_error,
)
from ragdocs.providers.websearch import WebSearchAuthError, WebSearchError

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
# Body of the q049 400 in M10 (docs/progress/M10-corrective-rag.md, S3 additional facts 3).
JSON_VALIDATE_BODY = {
    "error": {
        "message": "Failed to validate JSON. Please adjust your prompt. "
        "See 'failed_generation' for more details.",
        "type": "invalid_request_error",
        "code": "json_validate_failed",
        "failed_generation": "",
    }
}


def _status_error(cls: type[groq.APIStatusError], status: int, body: object) -> Exception:
    response = httpx.Response(status, request=REQUEST)
    return cls(f"Error code: {status} - {body}", response=response, body=body)


class _Model(pydantic.BaseModel):
    n: int


def _validation_error() -> pydantic.ValidationError:
    try:
        _Model.model_validate({"n": "not a number"})
    except pydantic.ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


def _other_400() -> Exception:
    body = {"error": {"type": "invalid_request_error", "code": "context_length_exceeded"}}
    return _status_error(groq.BadRequestError, 400, body)


STRUCTURED = {
    "json_validate_failed 400": lambda: _status_error(
        groq.BadRequestError, 400, JSON_VALIDATE_BODY
    ),
    "OutputParserException": lambda: OutputParserException("Failed to parse AnswerDraft"),
    "pydantic ValidationError": _validation_error,
}
NOT_STRUCTURED = {
    "other 400": (_other_400, "permanent"),
    "400 without a JSON body": (
        lambda: _status_error(groq.BadRequestError, 400, "plain text"),
        "permanent",
    ),
    "429": (lambda: _status_error(groq.RateLimitError, 429, {"error": {}}), "rate_limit"),
    "500": (lambda: _status_error(groq.InternalServerError, 500, None), "transient"),
    "503": (lambda: _status_error(groq.InternalServerError, 503, None), "transient"),
    "timeout": (lambda: groq.APITimeoutError(request=REQUEST), "transient"),
    "connection": (lambda: groq.APIConnectionError(request=REQUEST), "transient"),
    "401": (lambda: _status_error(groq.AuthenticationError, 401, None), "permanent"),
    "403": (lambda: _status_error(groq.PermissionDeniedError, 403, None), "permanent"),
    "web transient": (lambda: WebSearchError("x", kind="transient"), "transient"),
    "web permanent": (lambda: WebSearchError("x", kind="permanent"), "permanent"),
    "web auth": (lambda: WebSearchAuthError("x"), "permanent"),
    "ValueError": (lambda: ValueError("x"), "unclassified"),
    "RuntimeError": (lambda: RuntimeError("TAVILY_API_KEY missing"), "unclassified"),
}


@pytest.mark.parametrize("name", list(STRUCTURED))
def test_structured_output_errors_are_recognised(name: str) -> None:
    exc = STRUCTURED[name]()
    assert is_structured_output_error(exc) is True
    assert error_kind(exc) == "structured_output"


@pytest.mark.parametrize("name", list(NOT_STRUCTURED))
def test_other_errors_are_not_structured(name: str) -> None:
    build, kind = NOT_STRUCTURED[name]
    exc = build()
    assert is_structured_output_error(exc) is False
    assert error_kind(exc) == kind


def test_groq_error_code_reads_the_body() -> None:
    assert groq_error_code(STRUCTURED["json_validate_failed 400"]()) == "json_validate_failed"
    assert groq_error_code(_other_400()) == "context_length_exceeded"
    assert groq_error_code(ValueError("x")) is None


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("RateLimitError: Error code: 429 - {'error': {}}", "rate_limit"),
        ("RateLimitError", "rate_limit"),
        ("OutputParserException", "structured_output"),
        ("ValidationError: 1 validation error for AnswerDraft", "structured_output"),
        (
            "BadRequestError: Error code: 400 - {'error': {'code': 'json_validate_failed'}}",
            "structured_output",
        ),
        ("APIConnectionError: Connection error.", "transient"),
        ("APITimeoutError", "transient"),
        ("InternalServerError: Error code: 503", "transient"),
        ("AuthenticationError: Error code: 401", "permanent"),
        ("WebSearchAuthError", "permanent"),
        # Ambiguous by name alone: unclassified (M11 S1 human rule).
        ("BadRequestError", "unclassified"),
        ("BadRequestError: 400", "unclassified"),
        ("WebSearchError", "unclassified"),
        ("GraphRecursionError", "unclassified"),
        ("something new", "unclassified"),
        ("", "unclassified"),
    ],
)
def test_classify_message(message: str, kind: str) -> None:
    assert classify_message(message) == kind


def test_classify_message_uses_given_rate_limit_prefixes() -> None:
    assert classify_message("Throttled: slow down", ["Throttled"]) == "rate_limit"
    assert classify_message("RateLimitError", ["Throttled"]) == "unclassified"
