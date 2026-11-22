"""FastAPI application entrypoint for ragdocs."""

import asyncio
import importlib
import importlib.metadata
import json
import logging
import os
import platform
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from ragdocs.api.models import (
    ERR_INTERNAL,
    ERR_TOO_LARGE,
    AskRequest,
    QuestionError,
    validate_question,
)
from ragdocs.api.preflight import (
    BodyTooLarge,
    ask_preflight,
    body_size_guard,
    error_response,
    validation_message,
)
from ragdocs.api.ratelimit import LimitResult, RateLimiter, rate_limiter_dependency
from ragdocs.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE
from ragdocs.api.startup import validate_runtime_settings
from ragdocs.api.stream import NO_VALUE, StreamRunner, configure_request_logging, log_request
from ragdocs.config import Settings, get_settings
from ragdocs.pipelines import registry
from ragdocs.pipelines.base import Pipeline
from ragdocs.tracing import configure_tracing

logger = logging.getLogger(__name__)

PIPELINES: list[dict[str, str]] = [
    {
        "name": "baseline",
        "label": "Baseline RAG",
        "description": (
            "Retrieves documentation excerpts with hybrid search and answers from them "
            "in one LLM call."
        ),
    },
    {
        "name": "corrective",
        "label": "Corrective RAG",
        "description": (
            "Grades the retrieved excerpts, rewrites the query once if none are relevant, "
            "then falls back to a web search of the docs site."
        ),
    },
    {
        "name": "self_rag",
        "label": "Self-RAG",
        "description": (
            "Decides whether retrieval is needed, runs the corrective steps, then checks "
            "the answer against the excerpts and regenerates or abstains if it is unsupported."
        ),
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate runtime settings and configure tracing once at startup.

    A RuntimeError from validation (production only) stops the app from starting.
    """
    configure_request_logging()
    settings = get_settings()
    validate_runtime_settings(settings)
    app.state.tracing_active = configure_tracing(settings)
    yield


app = FastAPI(title="LangGraph Docs Assistant", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return the exact 422 body for a malformed request."""
    return error_response(422, validation_message(list(exc.errors())))


@app.exception_handler(QuestionError)
async def handle_question_error(_request: Request, exc: QuestionError) -> JSONResponse:
    """Return 422 with the question error message."""
    return error_response(422, exc.message)


@app.exception_handler(BodyTooLarge)
async def handle_body_too_large(_request: Request, _exc: BodyTooLarge) -> JSONResponse:
    """Return 413 for an oversized request body."""
    return error_response(413, ERR_TOO_LARGE)


@app.exception_handler(Exception)
async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
    """Return a generic 500; log the class and traceback, never the request body."""
    logger.error("Unhandled %s", type(exc).__name__, exc_info=exc)
    return error_response(500, ERR_INTERNAL)


REPO_ROOT = Path(__file__).resolve().parents[3]

# Mapping from distribution package name in requirements.txt to top-level importable module name.
PACKAGE_MODULE_MAP: dict[str, str] = {
    "google-genai": "google.genai",
    "tavily-python": "tavily",
}


def _find_requirements_file() -> Path:
    """Locate requirements.txt across local repository and Vercel environments."""
    candidates = [
        REPO_ROOT / "requirements.txt",
        Path.cwd() / "requirements.txt",
        Path(__file__).resolve().parents[3] / "requirements.txt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("requirements.txt could not be found.")


def _parse_requirements_packages(req_path: Path) -> list[str]:
    """Parse top-level package names from requirements.txt."""
    packages: list[str] = []
    with open(req_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            pkg_name = stripped.split("==")[0].split(">=")[0].split("<=")[0].strip()
            packages.append(pkg_name)
    return packages


@app.get("/api/health")
def get_health() -> dict[str, str]:
    """Return health status and deployment environment metadata."""
    settings = get_settings()
    commit_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "local")[:7]
    return {
        "status": "ok",
        "env": settings.env,
        "python": platform.python_version(),
        "commit": commit_sha,
    }


@app.get("/api/pipelines")
def get_pipelines() -> dict[str, list[dict[str, str]]]:
    """List the selectable pipelines."""
    return {"pipelines": PIPELINES}


# ---- POST /api/ask ----

_pipelines: dict[str, Pipeline] = {}
_pipeline_lock = threading.Lock()
KEYS_ALL = ("groq_api_key", "google_api_key")
KEYS_WEB = ("tavily_api_key",)


def get_pipeline(name: str) -> Pipeline:
    """Return the pipeline, building it once per process (call from the worker thread).

    Raises RuntimeError (from Settings.require) when a key the pipeline needs is unset.
    """
    settings = get_settings()
    needed = KEYS_ALL if name == "baseline" else KEYS_ALL + KEYS_WEB
    for key in needed:
        settings.require(key)
    with _pipeline_lock:
        if name not in _pipelines:
            _pipelines[name] = registry.get_pipeline(name)
        return _pipelines[name]


def reset_pipeline_cache() -> None:
    """Forget the built pipelines (for tests)."""
    with _pipeline_lock:
        _pipelines.clear()


class _RecordingLimiter:
    """Wraps the limiter and remembers the reason of the last check, for the log line."""

    def __init__(self, inner: RateLimiter) -> None:
        self._inner = inner
        self.reason: str | None = None

    def check(self, client_key: str) -> LimitResult:
        """Delegate to the wrapped limiter and record the reason."""
        result = self._inner.check(client_key)
        self.reason = result.reason
        return result


def _peek_body(body: bytes, settings: Settings) -> tuple[str, int | None]:
    """Return (pipeline name or "-", question length or None) for a request being refused."""
    try:
        parsed = AskRequest.model_validate(json.loads(body))
    except ValueError:
        return NO_VALUE, None
    try:
        return parsed.pipeline, len(validate_question(parsed.question, settings.max_question_chars))
    except QuestionError:
        return parsed.pipeline, None


def _log_refused(started: float, body: bytes, settings: Settings, reason: str | None) -> None:
    pipeline, chars = _peek_body(body, settings)
    limited = reason not in (None, "ok")
    log_request(
        pipeline,
        "limited" if limited else "invalid",
        int((time.monotonic() - started) * 1000),
        chars,
        limit_reason=reason if limited else None,
    )


@app.post("/api/ask", dependencies=[Depends(body_size_guard)], response_model=None)
async def ask(
    request: Request, limiter: Annotated[RateLimiter, Depends(rate_limiter_dependency)]
) -> StreamingResponse | JSONResponse:
    """Stream the pipeline's trace and answer as server-sent events."""
    started = time.monotonic()
    settings = get_settings()
    body = await request.body()
    recorder = _RecordingLimiter(limiter)
    # The limiter makes blocking HTTP calls, so keep them off the event loop.
    checked = await asyncio.to_thread(ask_preflight, request, body, recorder, settings)
    if isinstance(checked, JSONResponse):
        _log_refused(started, body, settings, recorder.reason)
        return checked
    question, pipeline_name = checked
    runner = StreamRunner(
        pipeline_name,
        question,
        settings,
        get_pipeline,
        bool(getattr(request.app.state, "tracing_active", False)),
        is_disconnected=request.is_disconnected,
        started_at=started,
    )
    return StreamingResponse(runner.events(), media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)


# Temporary: removed in M14.
@app.get("/api/deps-probe")
def get_deps_probe() -> dict[str, Any]:
    """Probe runtime package versions and import times for requirements.txt packages."""
    req_path = _find_requirements_file()
    packages = _parse_requirements_packages(req_path)

    results: list[dict[str, Any]] = []
    total_ms = 0.0

    for pkg in packages:
        module_name = PACKAGE_MODULE_MAP.get(pkg, pkg.replace("-", "_"))
        try:
            version = importlib.metadata.version(pkg)
        except Exception:
            version = "unknown"

        t0 = time.perf_counter()
        try:
            importlib.import_module(module_name)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
        except Exception:
            elapsed_ms = -1.0

        if elapsed_ms > 0:
            total_ms += elapsed_ms

        results.append(
            {
                "name": pkg,
                "version": version,
                "import_ms": round(elapsed_ms, 2),
            }
        )

    return {
        "packages": results,
        "total_ms": round(total_ms, 2),
    }
