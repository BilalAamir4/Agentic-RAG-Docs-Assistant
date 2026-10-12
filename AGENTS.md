Agent rules for Agentic-RAG-Docs-Assistant
Read this file fully at the start of every session, then docs/progress/PROGRESS.md, then the newest file in docs/progress/, then docs/DECISIONS.md, then the module prompt you were given.

Project in one paragraph
A documentation assistant over the LangGraph Python docs. Three pipelines (baseline LangChain RAG, corrective RAG and self-RAG in LangGraph) share one index, one answer prompt and one 50-question eval set, so their results are directly comparable. Offline (this Windows machine): ingest, index build, evaluation. Online (Vercel Hobby, Linux): static page in public/ plus a FastAPI function in api/index.py that loads the committed index into memory. Python package name: ragdocs.

Environment
Native Windows 11, PowerShell terminal. Not WSL. CI (GitHub Actions) and Vercel run Linux, so all code must work on both.
Run every project command through the task runner: py tasks.py <command>. Run a script directly with .venv\Scripts\python <path>. Never activate the venv and never call a bare python or pip.
Commands: setup, lint, format, test, test-live, tree, hash, ingest, index, eval --pipeline NAME, validate-eval [--require-verified], dev, bundle-check, smoke --url URL.
No make, sha256sum, tree, du or grep. Use py tasks.py hash for checksums, py tasks.py tree for the tree, Select-String or a short Python snippet for searching, and curl.exe (not curl) for HTTP.
Paths: pathlib everywhere; never hardcode separators; store repository-relative paths in data files with forward slashes (Path.as_posix()).
Text files: always read and write with encoding="utf-8"; write with newline="\n"; use ragdocs.io_utils for JSONL and text. The Windows default encoding is not UTF-8 and silently corrupts data.
Line endings: .gitattributes enforces LF; never commit CRLF files.
Hard rules
Scope: do only what the current module prompt asks. If something else looks necessary, add it under "Proposed follow-ups" in the tracking file instead of doing it.
Secrets: never create accounts, never ask for, print, log or commit API keys. Read secrets only through ragdocs.config.get_settings(). If a needed key is missing, stop and tell the human which env var to set in .env.
No invented facts: never guess model IDs, library APIs, CLI flags or URLs. Verify against the installed package source (importlib.metadata, reading .venv\Lib\site-packages) or official documentation, and record what you checked in the tracking file.
Dependencies: runtime packages go in requirements.txt, offline/test packages in requirements-dev.txt, always pinned with ==. Never add torch, transformers, sentence-transformers, chromadb, faiss, langchain-community or any Windows-only package to requirements.txt.
Import boundaries: ragdocs.ingest, ragdocs.eval and ragdocs.index.build are offline-only; nothing reachable from ragdocs.api may import them. Scripts in tools/ never import ragdocs; they are standalone and start with a docstring stating purpose, inputs, outputs. Scripts in scripts/ are thin CLIs over ragdocs functions.
Configuration: every tunable number, model ID and path lives in ragdocs.config.Settings. No magic numbers in logic.
Prompts: every LLM prompt is a module-level constant in a prompts.py file. The answer prompt in ragdocs/generation/prompts.py is shared by all three pipelines; change it only with a new entry in docs/DECISIONS.md.
Code quality: type hints and docstrings on all public functions; pydantic models (ragdocs.schemas) for any data crossing a module boundary; no bare except; functions under about 50 lines.
Tests: each module adds pytest tests. Unit tests never touch the network; mock external clients. Tests that call real APIs are marked @pytest.mark.live.
Verification: before finishing, run py tasks.py lint and py tasks.py test and paste the real summary lines into the tracking file. Never state that something passed without running it.
Git: commit only when the module prompt says to, and push only when it says to. Message format "MNN: imperative summary". Never add Co-authored-by or any other AI attribution trailer. Never change the origin remote.
Generated data (data/processed, data/index, results) is produced by scripts, never edited by hand. data/eval/eval_set.jsonl is the one file the human edits.
Ambiguity: when two reasonable readings of an instruction exist and the choice matters, stop and ask. Also record the question under "Open questions" in the tracking file.
Writing: plain and specific, numbers with units, no marketing language, no emoji.
Tracking file template (docs/progress/MNN-short-name.md)
MNN: Module name
Status: Done | Partial | Blocked
Date: YYYY-MM-DD

Goal
What was built (one line per file created or changed)
How to run
Verification (commands run and their actual output or numbers)
Decisions made (choice and reason; also append to docs/DECISIONS.md if it affects later modules)
Deviations from the prompt (and why)
Known issues and limitations
Open questions for the human
Proposed follow-ups (out of scope)
Prerequisites for the next module
After writing the tracking file, update that module's row in docs/progress/PROGRESS.md (status, date, link).
