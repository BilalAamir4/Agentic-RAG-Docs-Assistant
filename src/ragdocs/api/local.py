"""Local development server entry: the API plus the static page from public/.

Local only (uvicorn ragdocs.api.local:app). ragdocs.api.app never imports this module; on
Vercel the static files are served by the platform, not by FastAPI.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ragdocs.api.app import REPO_ROOT, app

PUBLIC_DIR = REPO_ROOT / "public"
LOCAL_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]


def configure_local(target: FastAPI, public_dir: Path) -> None:
    """Allow the local origins and mount public_dir at "/", after every API route."""
    target.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    target.mount("/", StaticFiles(directory=public_dir, html=True), name="public")


configure_local(app, PUBLIC_DIR)
