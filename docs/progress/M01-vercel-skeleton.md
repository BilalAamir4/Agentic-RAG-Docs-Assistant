M01: Vercel walking skeleton
Status: Done
Date: 2026-10-12

Resume audit (2026-10-12)

| Item | Status | Evidence |
|---|---|---|
| A1. Git index lock | VALID | `.git\index.lock` does not exist (`Test-Path .git\index.lock` returned False). |
| A1. Git fsck | VALID | `git fsck --no-dangling` exited 0 with no errors or corruption reported. |
| A1. Git branch & tracking | VALID | Current branch: `main`; tracking `origin/main`; ahead by 1 commit (`7aceeae M00: scaffold repository`). |
| A1. Git status | VALID | `git status --porcelain=v1` was clean at audit start. |
| A1. Git commit classification | NO_M01_COMMIT | Latest commit was M00 (`7aceeae`), no M01 commit existed locally or remotely. |
| A2. Protected files diff against M00 | VALID | `git diff --stat 7aceeae -- requirements.txt requirements-dev.txt pyproject.toml src/ragdocs/config.py src/ragdocs/schemas.py src/ragdocs/io_utils.py AGENTS.md` is empty (0 modifications). |
| A3. Python interpreter version | VALID | `.venv\Scripts\python --version` returned `Python 3.12.9`. |
| A3. Pip check | VALID | `.venv\Scripts\python -m pip check` returned `No broken requirements found.`. |
| A3. Requirements imports | VALID | All 14 packages in `requirements.txt` imported successfully in `.venv\Scripts\python`. |
| A4. Leftover temp bundle dirs | VALID | No `ragdocs-bundle-*` directories found in `$env:TEMP`. |
| A4. Port 8000 listener | VALID | `Get-NetTCPConnection -LocalPort 8000` reported nothing listening on port 8000. |
| A5. Research findings | MISSING | Documented in this file during Phase B. |
| A5. `src/ragdocs/api/app.py` | MISSING | Created during Phase B. |
| A5. `api/index.py` | INVALID | Existed as an unconfigured stub from M00 (`# implemented in M01`), implemented in Phase B. |
| A5. `vercel.json` | MISSING | Created during Phase B. |
| A5. `public/index.html` | INVALID | Existed as an unconfigured stub from M00 (`<!-- implemented in M11 -->`), implemented in Phase B. |
| A5. `public/health.js` | MISSING | Created during Phase B. |
| A5. `tools/bundle_size.py` | MISSING | Created during Phase B. |
| A5. `tasks.py` (`bundle-check`, `dev`) | INVALID | `cmd_dev` and `cmd_bundle_check` existed as stubs exiting 1, implemented in Phase B. |
| A5. `tests/test_api_health.py` | MISSING | Created during Phase B. |
| A5. `tests/test_import_boundaries.py` | MISSING | Created during Phase B. |
| A6. Linting check | VALID | `py tasks.py lint` passed (ruff check and ruff format passed, 24 files formatted). |
| A6. Unit tests | VALID | `py tasks.py test` passed (15 passed in 0.09s). |

Goal
Deploy a walking skeleton to Vercel Hobby hosting a static frontend and a FastAPI serverless function, verify runtime dependencies and Linux-wheel bundle size under 400 MB, and measure latency to decide the D2 gate.

Research findings (STEP 1)
- a) Python version selection:
  - Supported versions: Python 3.12 (default), 3.13, 3.14.
  - Selection mechanism: Defined via `project.requires-python` in `pyproject.toml`, or via `.python-version` containing the version string (e.g. `3.12`), or `Pipfile.lock`.
  - When `pyproject.toml` is absent/ignored, `.python-version` (3.12) is honored.
  - Reference: https://vercel.com/docs/functions/runtimes/python/python-version
- b) Dependency file precedence:
  - Vercel's runtime dependency resolution logic (`packages/python-analysis/src/manifest/package.ts` in `loadPythonManifest`) loads `pyproject.toml` first (`maybeLoadPyProjectToml`). Only if `pyproject.toml` does not exist does it fall back to `Pipfile.lock`, `Pipfile`, and `requirements.txt`.
  - Claim source: Verified directly in Vercel's open-source runtime builder repository `@vercel/python-analysis` (`https://github.com/vercel/vercel/blob/main/packages/python-analysis/src/manifest/package.ts#L426-L460`) and documented at https://vercel.com/docs/functions/runtimes/python.
  - Resolution: Added `pyproject.toml` to `.vercelignore` so Vercel ignores `pyproject.toml` during build and installs runtime dependencies directly from `requirements.txt`.
- c) Recommended FastAPI deployment pattern:
  - File-based entrypoint `api/index.py` with top-level `app = FastAPI()` is supported, routed via `vercel.json` rewrites or direct route mapping.
  - References: https://vercel.com/docs/functions/runtimes/python/api-directory and https://vercel.com/docs/frameworks/backend/fastapi
- d) Data files with `functions.includeFiles` and `.vercelignore` interaction:
  - Configured in `vercel.json` under `functions.<entrypoint>.includeFiles` accepting glob strings or string arrays.
  - `.vercelignore` controls which files are uploaded/included during deployment. If a path is matched in `.vercelignore`, it is not uploaded to Vercel, meaning `includeFiles` cannot bundle it.
  - Reference: https://vercel.com/docs/project-configuration/vercel-json#functions and https://vercel.com/docs/deployments/configure-a-build#preventing-upload-of-sensitive-or-unnecessary-files
- e) Max duration on Hobby:
  - Configured in `vercel.json` under `functions.<entrypoint>.maxDuration` in seconds. On Hobby, default and maximum allowed duration is 300 seconds (5 minutes).
  - Reference: https://vercel.com/docs/functions/configuring-functions/duration

What was built
- `src/ragdocs/api/app.py`: FastAPI application defining `/api/health` and `/api/deps-probe`.
- `api/index.py`: Serverless function entrypoint inserting `src` into `sys.path` and exporting `app`.
- `vercel.json`: Function duration (`maxDuration: 60`), `includeFiles` pattern, and rewrite rules.
- `public/index.html`: Valid HTML5 skeleton page loading health status via `public/health.js`.
- `public/health.js`: Client-side fetch script populating `/api/health` payload into pre element.
- `tools/bundle_size.py`: Standalone script checking Linux wheel bundle size against 400 MB limit.
- `tasks.py`: Updated `cmd_dev` (`uvicorn --reload --port 8000`) and `cmd_bundle_check`.
- `tests/test_api_health.py`: TestClient unit tests for `/api/health` and `/api/deps-probe`.
- `tests/test_import_boundaries.py`: Subprocess boundary test verifying no ingest/eval imports.
- `.vercelignore`: Appended `pyproject.toml` to ensure Vercel installs dependencies from `requirements.txt`.
- `docs/DECISIONS.md`: Appended D13 decision and recorded D2 gate results.
- `docs/progress/M01-vercel-skeleton.md`: Complete audit, implementation, and verification tracking.

How to run
- Lint checks: `py tasks.py lint`
- Unit tests: `py tasks.py test`
- Bundle size check: `py tasks.py bundle-check`
- Local dev server: `py tasks.py dev`

Verification
- Local lint checks (`py tasks.py lint`):
  ```text
  All checks passed!
  29 files already formatted
  Running ruff check...
  Running ruff format --check...
  ```
- Local unit tests (`py tasks.py test`):
  ```text
  ..................                                                       [100%]
  18 passed in 1.04s
  ```
- Local bundle check (`py tasks.py bundle-check`):
  ```text
  Total bundle size: 223.19 MB (limit: 400.00 MB)

  15 largest installed items:
    - numpy                                38.83 MB
    - numpy.libs                           26.19 MB
    - zstandard                            22.93 MB
    - cryptography                         14.69 MB
    - fastavro                             12.73 MB
    - google                               12.04 MB
    - tokenizers                           11.07 MB
    - hf_xet                               10.75 MB
    - langsmith                             6.69 MB
    - huggingface_hub                       6.33 MB
    - pydantic_core                         5.01 MB
    - langchain_core                        4.72 MB
    - tiktoken                              3.64 MB
    - pydantic                              3.58 MB
    - cohere                                3.51 MB
  ```
- Local dev server endpoints:
  - `curl.exe -s http://127.0.0.1:8000/api/health`:
    `{"status":"ok","env":"local","python":"3.12.9","commit":"local"}`
  - `curl.exe -s http://127.0.0.1:8000/api/deps-probe`:
    `{"packages":[{"name":"fastapi","version":"0.143.0","import_ms":0.01},{"name":"pydantic","version":"2.14.1","import_ms":0.01},{"name":"pydantic-settings","version":"2.15.0","import_ms":0.01},{"name":"numpy","version":"2.5.4","import_ms":82.08},{"name":"rank-bm25","version":"0.2.2","import_ms":0.83},{"name":"httpx","version":"0.28.1","import_ms":38.07},{"name":"langchain-core","version":"1.6.10","import_ms":3.53},{"name":"langgraph","version":"1.2.14","import_ms":0.43},{"name":"langchain-groq","version":"1.1.3","import_ms":535.6},{"name":"google-genai","version":"2.29.0","import_ms":339.83},{"name":"cohere","version":"7.2.0","import_ms":0.9},{"name":"tavily-python","version":"0.8.5","import_ms":174.94},{"name":"upstash-redis","version":"1.8.0","import_ms":13.22},{"name":"upstash-ratelimit","version":"1.2.0","import_ms":3.47}],"total_ms":1192.92}`
- Vercel Deployment Verification:
  - Production URL: `https://agentic-rag-docs-assistant.vercel.app/`
  - Vercel Build Log confirmation:
    - Built from commit: `c7aa86d`
    - Ignored `/pyproject.toml` per `.vercelignore`
    - `Using Python 3.12 from .python-version`
    - `Installing required dependencies from requirements.txt...`
    - `Compiling Python bytecode...`
  - Bundle Size:
    - Vercel function bundle: `76.0 MB` (Compressed) / `230.7 MB` (Uncompressed)
    - Local bundle-check: `223.19 MB`
  - Live Endpoint Timing (`curl.exe -s -o NUL -w "%{http_code} %{time_total}\n" https://agentic-rag-docs-assistant.vercel.app/api/health` 5x):
    ```text
    200 1.131172
    200 0.619251
    200 0.915522
    200 0.626013
    200 0.556620
    ```
  - Live Endpoint Payload (`https://agentic-rag-docs-assistant.vercel.app/api/health`):
    `{"status":"ok","env":"production","python":"3.12.14","commit":"c7aa86d"}`
  - Live Dependency Probe (`https://agentic-rag-docs-assistant.vercel.app/api/deps-probe`):
    `{"packages":[{"name":"fastapi","version":"0.143.0","import_ms":0.01},{"name":"pydantic","version":"2.14.1","import_ms":0.01},{"name":"pydantic-settings","version":"2.15.0","import_ms":0.01},{"name":"numpy","version":"2.5.4","import_ms":360.42},{"name":"rank-bm25","version":"0.2.2","import_ms":1.7},{"name":"httpx","version":"0.28.1","import_ms":68.3},{"name":"langchain-core","version":"1.6.10","import_ms":3.77},{"name":"langgraph","version":"1.2.14","import_ms":0.2},{"name":"langchain-groq","version":"1.1.3","import_ms":638.65},{"name":"google-genai","version":"2.29.0","import_ms":470.92},{"name":"cohere","version":"7.2.0","import_ms":4.66},{"name":"tavily-python","version":"0.8.5","import_ms":281.33},{"name":"upstash-redis","version":"1.8.0","import_ms":40.36},{"name":"upstash-ratelimit","version":"1.2.0","import_ms":5.7}],"total_ms":1876.04}`
    All 14 runtime packages from requirements.txt confirmed present and loaded.

Decisions made
- D2 Gate Decided: PASS (bundle size 223.19 MB local / 230.7 MB uncompressed Vercel < 400 MB; first call latency 1.13 s < 10 s). Recorded in `docs/DECISIONS.md`.
- D13: `.vercelignore` ignores `pyproject.toml` so Vercel installs runtime dependencies directly from `requirements.txt`.
- Linux wheel multi-platform in `tools/bundle_size.py`: added `--platform manylinux_2_28_x86_64` alongside `--platform manylinux2014_x86_64` because NumPy 2.5.4 requires glibc 2.28 wheels, which Vercel AL2023 (glibc 2.34) fully supports.

Deviations from the prompt
- `tools/bundle_size.py`: added `--platform manylinux_2_28_x86_64` in pip install flags so `numpy==2.5.4` binary wheel resolves on Windows without error.

Known issues and limitations
None.

Open questions for the human
None.

Proposed follow-ups (out of scope)
None.

Prerequisites for the next module
M01 complete; M02 docs ingestion and chunking can proceed.
