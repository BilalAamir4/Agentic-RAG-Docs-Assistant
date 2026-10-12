"""FastAPI application entrypoint for ragdocs."""

import importlib
import importlib.metadata
import os
import platform
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from ragdocs.config import get_settings

app = FastAPI(title="LangGraph Docs Assistant")

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


# Temporary: removed in M12.
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
