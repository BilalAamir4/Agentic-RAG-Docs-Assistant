"""Rate limiting for the public API: per-client hourly window plus a daily global cap.

Runtime-safe module: imports only upstash packages, httpx and ragdocs.config. Client IPs
are hashed before use as keys and are never logged (D10, D28).
"""

import hashlib
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

import httpx
from starlette.requests import Request
from upstash_ratelimit import FixedWindow, Ratelimit
from upstash_redis import Redis

from ragdocs.config import Settings, get_settings

logger = logging.getLogger(__name__)

IP_PREFIX = "ragdocs:ip"
GLOBAL_KEY_PREFIX = "ragdocs:global:"
IP_WINDOW_S = 3600
GLOBAL_KEY_TTL_S = 172800
KEY_HEX_CHARS = 16

Reason = Literal["ok", "ip", "global", "unavailable"]


@dataclass(frozen=True)
class LimitResult:
    """Outcome of a rate-limit check."""

    allowed: bool
    retry_after_s: int
    reason: Reason


class RateLimiter(Protocol):
    """Anything that can decide whether a client may make a request."""

    def check(self, client_key: str) -> LimitResult:
        """Return the decision for one request from the hashed client key."""
        ...


def client_key(ip: str, salt: str | None) -> str:
    """Return the first 16 hex characters of sha256(salt + ip)."""
    digest = hashlib.sha256(((salt or "") + ip).encode("utf-8")).hexdigest()
    return digest[:KEY_HEX_CHARS]


def client_ip(request: Request) -> str:
    """Return the first X-Forwarded-For entry, else the socket peer, else "unknown"."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _seconds_to_next_utc_midnight(now: float) -> int:
    """Whole seconds from now (unix time) to the next 00:00 UTC, at least 1."""
    moment = datetime.fromtimestamp(now, tz=UTC)
    midnight = (moment + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, math.ceil((midnight - moment).total_seconds()))


def build_redis(settings: Settings) -> Redis:
    """Build a sync Upstash client with no retry sleep and a bounded HTTP timeout.

    upstash-redis 1.8.0 creates httpx.Client(timeout=None) and retries once after 3 s, so
    both are overridden here (the client exposes no timeout parameter).
    """
    redis = Redis(
        url=settings.require("upstash_redis_rest_url"),
        token=settings.require("upstash_redis_rest_token"),
        rest_retries=0,
    )
    redis._http._client.timeout = httpx.Timeout(settings.upstash_timeout_s)  # noqa: SLF001
    return redis


class UpstashRateLimiter:
    """Per-client fixed window, then a global daily counter. Fails closed on errors."""

    def __init__(
        self,
        settings: Settings,
        *,
        redis: Any = None,
        ip_limiter: Any = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._settings = settings
        self._redis = redis if redis is not None else build_redis(settings)
        self._ip_limiter = ip_limiter or Ratelimit(
            redis=self._redis,
            limiter=FixedWindow(settings.rate_limit_per_ip_per_hour, IP_WINDOW_S, "s"),
            prefix=IP_PREFIX,
        )
        self._clock = clock

    def check(self, client_key: str) -> LimitResult:
        """Check the per-client window, then the global daily counter."""
        try:
            return self._check(client_key)
        except Exception as exc:  # fail closed on any Upstash or network error (D28)
            logger.warning("Rate limiter unavailable: %s", type(exc).__name__)
            return LimitResult(False, 0, "unavailable")

    def _check(self, key: str) -> LimitResult:
        response = self._ip_limiter.limit(key)
        now = self._clock()
        if not response.allowed:
            return LimitResult(False, max(1, math.ceil(response.reset - now)), "ip")
        day = datetime.fromtimestamp(now, tz=UTC).strftime("%Y%m%d")
        global_key = f"{GLOBAL_KEY_PREFIX}{day}"
        count = self._redis.incr(global_key)
        if count == 1:
            self._redis.expire(global_key, GLOBAL_KEY_TTL_S)
        if count > self._settings.daily_global_cap:
            return LimitResult(False, _seconds_to_next_utc_midnight(now), "global")
        return LimitResult(True, 0, "ok")


class DisabledRateLimiter:
    """Allows every request; used only outside production without Upstash settings."""

    def check(self, client_key: str) -> LimitResult:
        """Always allow."""
        return LimitResult(True, 0, "ok")


_warned_disabled = False
_process_limiter: RateLimiter | None = None


def _has_upstash(settings: Settings) -> bool:
    return all(
        v is not None and v.get_secret_value()
        for v in (settings.upstash_redis_rest_url, settings.upstash_redis_rest_token)
    )


def get_rate_limiter(settings: Settings) -> RateLimiter:
    """Return the Upstash limiter, or a disabled one (with one warning) outside production."""
    global _warned_disabled
    if _has_upstash(settings):
        return UpstashRateLimiter(settings)
    if settings.env == "production":
        raise RuntimeError(
            "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required in production."
        )
    if not _warned_disabled:
        _warned_disabled = True
        logger.warning("Upstash settings are missing; rate limiting is disabled.")
    return DisabledRateLimiter()


def rate_limiter_dependency() -> RateLimiter:
    """FastAPI dependency: the process-wide limiter, built on first use."""
    global _process_limiter
    if _process_limiter is None:
        _process_limiter = get_rate_limiter(get_settings())
    return _process_limiter


def reset_rate_limiter_state() -> None:
    """Clear the cached limiter and the warning flag (for tests)."""
    global _process_limiter, _warned_disabled
    _process_limiter = None
    _warned_disabled = False
