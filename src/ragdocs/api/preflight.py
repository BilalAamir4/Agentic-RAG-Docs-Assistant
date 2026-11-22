"""Request checks that run before the streaming route does any work."""

import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ragdocs.api.models import (
    ERR_BAD_JSON,
    ERR_PIPELINE,
    ERR_TOO_LARGE,
    AskRequest,
    QuestionError,
    validate_question,
)
from ragdocs.api.ratelimit import RateLimiter, client_ip, client_key
from ragdocs.config import Settings, get_settings


class BodyTooLarge(Exception):
    """Content-Length or the actual body exceeds max_body_bytes."""


def validation_message(errors: list[Any]) -> str:
    """Map pydantic error entries for AskRequest to the exact client-facing message."""
    locs = {e["loc"][-1] for e in errors if e.get("loc")}
    if "question" in locs or not locs:
        return ERR_BAD_JSON
    if "pipeline" in locs:
        return ERR_PIPELINE
    return ERR_BAD_JSON


def _declared_too_large(request: Request, settings: Settings) -> bool:
    declared = request.headers.get("content-length")
    return declared is not None and declared.isdigit() and int(declared) > settings.max_body_bytes


def body_size_guard(request: Request) -> None:
    """Dependency: reject a declared Content-Length above max_body_bytes (before parsing)."""
    if _declared_too_large(request, get_settings()):
        raise BodyTooLarge


def error_response(status: int, message: str, **extra: Any) -> JSONResponse:
    """Return a JSON error body {"error": message, ...}."""
    return JSONResponse({"error": message, **extra}, status_code=status)


def _parse_body(body: bytes) -> AskRequest | JSONResponse:
    try:
        raw = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return error_response(422, ERR_BAD_JSON)
    if not isinstance(raw, dict):
        return error_response(422, ERR_BAD_JSON)
    try:
        return AskRequest.model_validate(raw)
    except ValueError as exc:  # pydantic.ValidationError subclasses ValueError
        errors = exc.errors() if hasattr(exc, "errors") else []
        return error_response(422, validation_message(errors))


def _limit_response(limiter: RateLimiter, key: str) -> JSONResponse | None:
    result = limiter.check(key)
    if result.reason == "ip":
        return JSONResponse(
            {
                "error": "Rate limit reached. Try again later.",
                "retry_after_s": result.retry_after_s,
            },
            status_code=429,
            headers={"Retry-After": str(result.retry_after_s)},
        )
    if result.reason == "global":
        return error_response(503, "The demo's daily budget is used up. It resets at 00:00 UTC.")
    if result.reason == "unavailable":
        return error_response(503, "The service is temporarily unavailable.")
    return None


def ask_preflight(
    request: Request, body: bytes, limiter: RateLimiter, settings: Settings
) -> tuple[str, str] | JSONResponse:
    """Check body size, validate the question, then rate limit.

    Returns (stripped question, pipeline name) or the error response to send. An invalid
    request never reaches the limiter.
    """
    declared = request.headers.get("content-length")
    too_big = (
        declared is not None and declared.isdigit() and int(declared) > settings.max_body_bytes
    )
    if too_big or len(body) > settings.max_body_bytes:
        return error_response(413, ERR_TOO_LARGE)
    parsed = _parse_body(body)
    if isinstance(parsed, JSONResponse):
        return parsed
    try:
        question = validate_question(parsed.question, settings.max_question_chars)
    except QuestionError as exc:
        return error_response(422, exc.message)
    key = client_key(client_ip(request), _salt(settings))
    blocked = _limit_response(limiter, key)
    return blocked if blocked is not None else (question, parsed.pipeline)


def _salt(settings: Settings) -> str | None:
    return settings.ip_hash_salt.get_secret_value() if settings.ip_hash_salt else None
