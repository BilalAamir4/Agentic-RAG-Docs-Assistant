"""Local development server entry: the API plus the static page from public/.

Local only (uvicorn ragdocs.api.local:app). ragdocs.api.app never imports this module; on
Vercel the static files are served by the platform, not by FastAPI. Production headers are
set in vercel.json (M14); this module sends the same Content-Security-Policy locally so every
local browser check runs under the production policy.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ragdocs.api.app import REPO_ROOT, app
from ragdocs.api.ratelimit import LimitResult, RateLimiter, rate_limiter_dependency

PUBLIC_DIR = REPO_ROOT / "public"
LOCAL_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

# The M14 policy, character for character.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)

FAKE_LIMIT_ENV = "RAGDOCS_LOCAL_FAKE_LIMIT"
FAKE_LIMIT_RETRY_AFTER_S = 5
FAKE_LIMIT_REASONS = ("ip", "global")

logger = logging.getLogger("ragdocs.api.local")


class CspMiddleware:
    """Pure ASGI middleware that adds the Content-Security-Policy header to every response.

    Not BaseHTTPMiddleware: that wraps the body stream and would change how a client
    disconnect reaches the SSE generator (D29).
    """

    def __init__(self, inner: ASGIApp) -> None:
        self.inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Forward the request, adding the header to the response start message."""
        if scope["type"] != "http":
            await self.inner(scope, receive, send)
            return

        async def send_with_csp(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"content-security-policy", CSP.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.inner(scope, receive, send_with_csp)


class FakeLimiter:
    """A limiter that refuses every request with a fixed reason (local testing only)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def check(self, client_key: str) -> LimitResult:
        """Refuse the request."""
        return LimitResult(
            allowed=False,
            retry_after_s=FAKE_LIMIT_RETRY_AFTER_S,
            reason=self.reason,  # type: ignore[arg-type]
        )


def parse_fake_limit(value: str | None) -> str | None:
    """Return None for unset or empty, "ip" or "global"; raise ValueError for anything else."""
    if not value:
        return None
    if value not in FAKE_LIMIT_REASONS:
        raise ValueError(f"{FAKE_LIMIT_ENV} must be unset, empty, 'ip' or 'global'; got {value!r}")
    return value


def apply_fake_limit(target: FastAPI, reason: str | None) -> None:
    """Override the rate limiter dependency of target with a FakeLimiter, if reason is set."""
    if reason is None:
        return
    limiter: RateLimiter = FakeLimiter(reason)
    target.dependency_overrides[rate_limiter_dependency] = lambda: limiter
    logger.warning(
        "%s=%s: every /api/ask request is refused with a fake %s limit",
        FAKE_LIMIT_ENV,
        reason,
        reason,
    )


def configure_local(target: FastAPI, public_dir: Path) -> None:
    """Add the CSP header and local CORS, and mount public_dir at "/" after every API route."""
    target.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    target.add_middleware(CspMiddleware)
    target.mount("/", StaticFiles(directory=public_dir, html=True), name="public")


configure_local(app, PUBLIC_DIR)
apply_fake_limit(app, parse_fake_limit(os.environ.get(FAKE_LIMIT_ENV)))
