"""FastAPI application entrypoint for ragdocs."""

import importlib
import importlib.metadata
import logging
import os
import platform
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ragdocs.api.models import ERR_INTERNAL, ERR_TOO_LARGE, QuestionError
from ragdocs.api.preflight import BodyTooLarge, error_response, validation_message
from ragdocs.api.startup import validate_runtime_settings
from ragdocs.config import get_settings

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
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate runtime settings once at startup (raises in production when unsafe)."""
    validate_runtime_settings(get_settings())
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
