M00: Scaffold and conventions
Status: Done
Date: 2026-10-12

Goal
Create the complete folder structure, project configuration, cross-platform task runner (tasks.py), standing agent rules (AGENTS.md), shared pydantic data models, settings, logging, tracking files, and tests so that setup, lint, and test all pass on Windows and Linux without implementing RAG logic.

What was built
- `AGENTS.md`: Standing agent rules, architecture constraints, and tracking conventions.
- `.gitattributes`: Line ending enforcement (`* text=auto eol=lf`) and binary flags for npy/png/gif.
- `.gitignore`: Ignore rules for venv, caches, raw data, egg-info, and environment files.
- `.python-version`: Python version pinning (3.12).
- `.vercelignore`: Deployment ignore list excluding offline artifacts and tooling.
- `.env.example`: Template environment variable definitions with descriptive comments.
- `pyproject.toml`: Setuptools package build definition, ruff linting config, and pytest options.
- `requirements.txt`: Runtime dependencies pinned to exact installed versions for Vercel deployment.
- `requirements-dev.txt`: Development and testing dependencies pinned to exact installed versions.
- `tasks.py`: Standard-library cross-platform task runner for Windows and Linux.
- `src/ragdocs/__init__.py`: Root package docstring.
- `src/ragdocs/config.py`: Pydantic settings loading and path resolution from repo root.
- `src/ragdocs/io_utils.py`: Deterministic UTF-8 and LF newline read/write helpers for text and JSONL.
- `src/ragdocs/schemas.py`: Pydantic models for chunks, evidence, eval items, citations, and traces.
- `src/ragdocs/logging_setup.py`: Standard library stream logging without secret leakage.
- `src/ragdocs/providers/__init__.py`: Subpackage init.
- `src/ragdocs/ingest/__init__.py`: Subpackage init.
- `src/ragdocs/index/__init__.py`: Subpackage init.
- `src/ragdocs/retrieval/__init__.py`: Subpackage init.
- `src/ragdocs/generation/__init__.py`: Subpackage init.
- `src/ragdocs/pipelines/__init__.py`: Subpackage init.
- `src/ragdocs/pipelines/agentic/__init__.py`: Subpackage init.
- `src/ragdocs/eval/__init__.py`: Subpackage init.
- `src/ragdocs/api/__init__.py`: Subpackage init.
- `api/index.py`: API entrypoint placeholder for M01.
- `public/index.html`: Web UI frontend placeholder for M11.
- `docs/DECISIONS.md`: Initial architectural decisions D1 through D12.
- `docs/architecture.md`: Two-paragraph offline/online architecture summary with repository tree.
- `docs/progress/PROGRESS.md`: Module progress tracker matrix.
- `tests/test_schemas.py`: Unit tests for EvalItem validation rules and chunk normalization.
- `tests/test_config.py`: Unit tests for Settings defaults, require() checks, and path independence.
- `tests/test_io_utils.py`: Unit tests for LF newlines, no carriage returns, and unicode round-trips.
- `.gitkeep` files in `scripts/`, `tools/`, `results/runs/`, `data/processed/`, `data/index/`, `data/eval/`.

How to run
- Setup environment: `py -3.12 tasks.py setup`
- Run linting: `py tasks.py lint`
- Format code: `py tasks.py format`
- Run unit tests: `py tasks.py test`
- Display repository tree: `py tasks.py tree`
- Checksum files: `py tasks.py hash pyproject.toml tasks.py`

Verification
Step 0 Pre-flight outputs:
- `py -3.12 --version`: `Python 3.12.9`
- `git remote get-url origin`: `https://github.com/BilalAamir4/Agentic-RAG-Docs-Assistant-.git`
- `git status`: `On branch main / nothing to commit, working tree clean`
- `git log --oneline -1`: `f606d48 Remove README file`
- `Get-ChildItem -Force`: shows only `.git`
- `git config core.longpaths true`: exit code 0
- `git config core.autocrlf false`: exit code 0

Setup and validation commands:
- `py -3.12 tasks.py setup`: Virtualenv `.venv` created, pip upgraded, dependencies installed, package installed in editable mode (`ragdocs==0.1.0`). Exit code 0.
- `py tasks.py lint`:
  ```text
  All checks passed!
  23 files already formatted
  ```
  Exit code 0.
- `py tasks.py test`:
  ```text
  ...............                                                          [100%]
  15 passed in 0.12s
  ```
  Exit code 0.
- `.venv\Scripts\python -c "from ragdocs.config import get_settings; print(get_settings().index_dir)"`:
  `C:\Users\Bilal Aamir\Documents\GitHub\RAG Docs Assistant\data\index`
- `py tasks.py ingest`:
  `Not implemented yet: added in module M02`
  Exit code 1.
- `py tasks.py tree`:
  ```text
  .
  ├── api/
  │   └── index.py
  ├── data/
  │   ├── eval/
  │   │   └── .gitkeep
  │   ├── index/
  │   │   └── .gitkeep
  │   └── processed/
  │       └── .gitkeep
  ├── docs/
  │   ├── progress/
  │   │   ├── M00-scaffold.md
  │   │   └── PROGRESS.md
  │   ├── architecture.md
  │   └── DECISIONS.md
  ├── public/
  │   └── index.html
  ├── results/
  │   └── runs/
  │       └── .gitkeep
  ├── scripts/
  │   └── .gitkeep
  ├── src/
  │   └── ragdocs/
  │       ├── api/
  │       │   └── __init__.py
  │       ├── eval/
  │       │   └── __init__.py
  │       ├── generation/
  │       │   └── __init__.py
  │       ├── index/
  │       │   └── __init__.py
  │       ├── ingest/
  │       │   └── __init__.py
  │       ├── pipelines/
  │       │   ├── agentic/
  │       │   │   └── __init__.py
  │       │   └── __init__.py
  │       ├── providers/
  │       │   └── __init__.py
  │       ├── retrieval/
  │       │   └── __init__.py
  │       ├── __init__.py
  │       ├── config.py
  │       ├── io_utils.py
  │       ├── logging_setup.py
  │       └── schemas.py
  ├── tests/
  │   ├── test_config.py
  │   ├── test_io_utils.py
  │   └── test_schemas.py
  ├── tools/
  │   └── .gitkeep
  ├── .env.example
  ├── .gitattributes
  ├── .gitignore
  ├── .python-version
  ├── .vercelignore
  ├── AGENTS.md
  ├── pyproject.toml
  ├── requirements-dev.txt
  ├── requirements.txt
  └── tasks.py
  ```

Decisions made
- D1 to D12 recorded in `docs/DECISIONS.md`. In particular D12 addresses native Windows 11 development with LF normalization and cross-platform task runner.

Deviations from the prompt
None.

Known issues and limitations
None.

Open questions for the human
- The GitHub remote origin URL has a trailing hyphen (`Agentic-RAG-Docs-Assistant-.git`), which GitHub automatically redirects to `Agentic-RAG-Docs-Assistant.git`. Per the pre-flight instructions not to modify remotes, it remains as configured.

Proposed follow-ups (out of scope)
None.

Prerequisites for the next module
M01 requires implementing the walking skeleton FastAPI app and static HTML on Vercel.
