M07: LangSmith tracing and plan sync
Status: Done
Date: 2026-11-15

Goal
When tracing is enabled, every question run through a pipeline produces one LangSmith trace: a parent run named after the pipeline, a `hybrid_retrieve` retriever child showing the retrieved chunks, and a `generate` child containing the ChatGroq call. When tracing is disabled, outputs are identical to M06 and no LangSmith client is constructed. Also sync PROGRESS.md and DECISIONS.md to the M07 to M15 plan.

What was built
- docs/progress/PROGRESS.md: replaced M07 to M13 rows with M07 to M15 (M00 to M06 unchanged).
- docs/DECISIONS.md: appended D18 (LangSmith role), D19 (RAGAS role), D20 (citation scoring), D21 (module order), D22 (context metrics and trace naming).
- requirements.txt: pinned `langsmith==0.14.7` (already installed as a dependency of langchain-core 1.6.10).
- src/ragdocs/config.py: added `langsmith_api_key`, `langsmith_tracing`, `langsmith_project`, `langsmith_endpoint`, `langsmith_sampling_rate` (env `LANGSMITH_TRACING_SAMPLING_RATE`, validated 0 to 1).
- .env.example: added the five LangSmith variables with comments.
- src/ragdocs/tracing.py: new. `configure_tracing`, `traced_run`, `TracedRun`, `tracing_enabled`, `flush_traces`, `last_trace_url`.
- src/ragdocs/pipelines/baseline.py: `stream(question, run_metadata=None)` wraps the run in a parent run named after the pipeline; retrieval runs inside a `hybrid_retrieve` retriever run; the LLM call passes `run_name="generate"` and the metadata alongside the existing callbacks. Removed the `except TypeError` re-invoke fallback. Split into helpers (`_retrieve_traced`, `_generate`, `_stream_events`, `_parent_outputs`, `_chunk_summary`, `_as_trace_document`) to keep functions under about 50 lines.
- src/ragdocs/pipelines/base.py: `Pipeline.stream` protocol gains optional `run_metadata`.
- scripts/ask.py: calls `configure_tracing(get_settings())` first, `flush_traces()` in a `finally`, and prints the trace URL when tracing is active.
- tests/test_baseline_snapshot.py and tests/fixtures/baseline_stream_snapshot.json: snapshot of events and timing-free PipelineResult, generated from the unchanged M06 code.
- tests/conftest.py: autouse fixture forcing tracing off for non-live tests and clearing the settings and langsmith env caches.
- tests/test_tracing.py: configure_tracing cases, .env override test, disabled no-client tests, enabled nesting test with a fake client, import-boundary test.
- tests/test_generation.py: `StubStructuredLLM.invoke` now takes `config=None` explicitly.

How to run
- Enable tracing: set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=ragdocs-local` in .env.
- `.venv\Scripts\python scripts\ask.py --pipeline baseline "question"` prints a `LangSmith trace: <url>` line at the end when tracing is active.
- Disable for one process: set `LANGSMITH_TRACING=false` in the process environment (real env overrides .env).

Verification

Step 1 findings
a) Env var names. Source: .venv\Lib\site-packages\langsmith\utils.py `get_env_var` (namespaces `("LANGSMITH", "LANGCHAIN")`, `functools.lru_cache(maxsize=100)`), `tracing_is_enabled`, `get_api_url`, `get_api_key`, `get_tracer_project`. Docs: https://docs.langchain.com/langsmith/observability-quickstart, https://docs.langchain.com/langsmith/trace-with-langchain.
   - Enable: `LANGSMITH_TRACING=true`. `tracing_is_enabled` reads `get_env_var("TRACING_V2", default=get_env_var("TRACING"))`, so the lookup order is LANGSMITH_TRACING_V2, LANGCHAIN_TRACING_V2, LANGSMITH_TRACING, LANGCHAIN_TRACING. The first non-empty value wins and must equal "true".
   - API key `LANGSMITH_API_KEY`, project `LANGSMITH_PROJECT` (fallback `*_SESSION`, default "default"), endpoint `LANGSMITH_ENDPOINT` (default https://api.smith.langchain.com).
   - Older LANGCHAIN_* names are still honoured by the source as a fallback for every name. The current docs do not mention LANGCHAIN_TRACING_V2 or LANGCHAIN_API_KEY.
   - Lookups are lru_cached, so ragdocs.tracing clears `get_env_var` and `get_tracer_project` caches after changing env vars.
   - Docs note: the quickstart now steers new workspaces to `LANGSMITH_AGENT_ID` / `LANGSMITH_AGENT_ENVIRONMENT`; it says project-based workspaces set `LANGSMITH_PROJECT`. This account accepted project-based tracing.
b) Tracer attachment. Source: langchain_core\callbacks\manager.py `_configure` and langchain_core\tracers\context.py `_tracing_v2_is_enabled`. On every runnable call, `_configure` checks `_tracing_v2_is_enabled()` (which calls `langsmith.utils.tracing_is_enabled()`) and adds a `LangChainTracer` if none is already among the handlers. Explicit `config={"callbacks": [...]}` handlers are copied first, then the tracer is added, so passing CallCounter does not prevent tracing. The parent run id is taken from `get_tracing_context()["parent"]`, which is how LangChain runs nest under a langsmith `trace`.
c) Parent run API. Source: langsmith\run_helpers.py `class trace` (sync and async context manager). Signature: `trace(name, run_type="chain", *, inputs, project_name, parent, tags, metadata, client, run_id, ...)`. Yields a `RunTree`; outputs via `run_tree.end(outputs=...)` (or `end(error=...)`), patched on exit. Metadata and tags are constructor arguments. Run id is `run_tree.id`; URL is `run_tree.get_url()` (langsmith\run_trees.py; makes a network call to resolve the project, cached per run). `traceable` exists too, but `trace` fits the imperative generator code.
d) Retriever rendering. Docs: https://docs.langchain.com/langsmith/log-retriever-trace says to return a list of dicts with `page_content`, `type` ("Document") and `metadata`. LangChain's own retriever runs store outputs as `{"documents": [...]}` (langchain_core\tracers\core.py, `_complete_retrieval_run`), so outputs are `{"documents": [{"page_content", "type": "Document", "metadata": {chunk_id, url, rank, score}}]}`.
e) Flush. Docs (trace-with-langchain, "Ensure all traces are submitted before exiting"): `from langchain_core.tracers.langchain import wait_for_all_tracers`. Source: it calls `rt._CLIENT.flush()` only if a client already exists, so it never builds one. `Client.flush(timeout=None)` is in langsmith\client.py.
f) Sampling and masking. `LANGSMITH_TRACING_SAMPLING_RATE` (float 0 to 1; langsmith\client.py `_get_tracing_sampling_rate`; docs https://docs.langchain.com/langsmith/sample-traces). `LANGSMITH_HIDE_INPUTS`, `LANGSMITH_HIDE_OUTPUTS`, also `LANGSMITH_HIDE_METADATA` (langsmith\client.py; docs https://docs.langchain.com/langsmith/mask-inputs-outputs). The sampling field was added to Settings; hide vars were not (not requested).
g) Free plan. https://www.langchain.com/pricing: Developer plan "Up to 5k base traces / mo, then pay-as-you-go", 1 seat, $0. FAQ: "Base traces have a shorter retention period of 14 days. Extended traces have a longer retention period of 180 days."

Tests and lint (final run)
- `py tasks.py lint`: "All checks passed!", "92 files already formatted".
- `py tasks.py test`: "89 passed, 1 deselected in 2.54s".
- Snapshot test passed before any change to baseline.py (fixture generated from commit bfc7412 code) and after.
- Removing the TypeError fallback broke no test other than stub signatures; the only StructuredLLM stub (tests/test_generation.py) already accepted `**kwargs` and now takes `config=None`.
- `py tasks.py bundle-check`: "Total bundle size: 229.46 MB (limit: 400.00 MB)"; langsmith 6.69 MB was already in the bundle.

Live check (2026-11-15)
- q001 run with tracing on: answer with 3 citations, LLM calls 1, latency 2274 ms, trace URL printed.
- Trace structure read back with `langsmith.Client().list_runs(trace_id=...)`:
  ```
  baseline [chain] parent=-
    hybrid_retrieve [retriever] parent=baseline
    generate [chain] parent=baseline
      ChatGroq [llm] parent=generate
      PydanticToolsParser [parser] parent=generate
  ```
- Screenshot: docs/screenshots/langsmith-baseline-trace.png (1642 x 938 PNG), saved by the human (this session had no browser tool).

LangSmith deprecation notice (2026-11-15)
- After the live check, the LangSmith UI showed: API key "rag-docs-assisstant" "still calls 1 deprecated endpoint", `POST /runs/query`, caller langsmith-py/0.14.x, stops working on January 31, 2027. Guide: https://docs.langchain.com/langsmith/smithdb-sdk-migration-query-runs#runs-query
- Cause: the one-off read-back above, `langsmith.Client().list_runs(trace_id=...)`, run from the command line during this module. It also printed "list_runs() is deprecated and will be removed after Jan 31, 2027. Use client.runs.query() instead."
- Repo search: in langsmith 0.14.7 (.venv\Lib\site-packages\langsmith\client.py), `/runs/query` is called only from `Client.list_runs` (line 4641), `Client.list_threads` (line 4742) and the public shared-run path (line 5153). A search of src, scripts, tests, tools, api and tasks.py for `list_runs`, `list_threads`, `runs/query`, `runs.query` and `read_run` found no matches. The tracing path (`run_helpers.trace`, `RunTree.post/patch`, `RunTree.get_url`, `wait_for_all_tracers`) does not use `/runs/query`.
- Result: no code change, no SDK upgrade. The notice should clear once no further `list_runs` calls are made. Any future run read-back (for example M09 experiment upload) must use `client.runs.query()` per the guide.
- Overhead check, q001, 10 runs alternating on/off, 10 s apart, latency_ms from ask.py:
  - Tracing on: 1827, 1655, 1700, 1696, 1628; median 1696 ms.
  - Tracing off (LANGSMITH_TRACING=false in process env): 1716, 1783, 1747, 2199, 1760; median 1760 ms.
  - No overhead visible at this sample size; the on/off gap (64 ms) is smaller than run-to-run spread. No code changed based on this.
- .env keeps `LANGSMITH_TRACING=true` (the off runs set the variable only in the child process environment).

Decisions made
- Disabled tracing writes `LANGSMITH_TRACING=false` and also `LANGSMITH_TRACING_V2=false`, by direct assignment. Reason: `*_TRACING_V2` is checked before `*_TRACING`, so a leftover `LANGCHAIN_TRACING_V2=true` in the shell would otherwise keep tracing on.
- `traced_run` decides enabled/disabled with `langsmith.utils.tracing_is_enabled()`, so it also respects `tracing_context(enabled=...)`. When disabled it yields a no-op handle and never calls langsmith.
- Retriever outputs use the `documents` key, matching LangChain retriever runs.
- `ask.py` gets the trace URL from `ragdocs.tracing.last_trace_url()`, which keeps a reference to the most recent root run. The pipeline stream cannot return a run id without changing its events.
- Failed runs: the parent run is marked with the same safe error message as the error event.
- Parent run name uses `self.name` (default "baseline"), consistent with D22.

Deviations from the prompt
- .env.example: non-secret LangSmith lines carry their defaults (`false`, `ragdocs-local`, `1.0`) instead of empty values, because an empty value fails Settings validation for bool and float fields. Key and endpoint lines are empty.
- tests/conftest.py also sets `LANGSMITH_TRACING_V2=false` (in addition to LANGSMITH_TRACING and LANGCHAIN_TRACING_V2), because it has the highest precedence. It also clears langsmith's env caches and removes LANGSMITH_*/LANGCHAIN_* vars written directly by configure_tracing during a test.
- Overhead runs alternated on/off instead of 5 then 5, so drift affects both sets equally.
- Screenshot taken by the human; no browser tool was available. Nesting was verified through the LangSmith API instead.

Known issues and limitations
- `stream()` is a generator; the parent run stays open while the consumer handles each event. If a consumer abandons the generator early, the run closes with a GeneratorExit error when the generator is closed or collected.
- After `configure_tracing` has run with tracing off, `LANGSMITH_TRACING_V2=false` stays in os.environ for the process. Enabling tracing later in the same process requires removing it.
- `last_trace_url()` makes network calls (project lookup), only when tracing is active.
- The LCEL `self.chain` attribute is still not used by `stream()` and is not traced with these names.

Open questions for the human
- None.

Proposed follow-ups (out of scope)
- `.env.example` has `RAGDOCS_ENV=` empty, which fails Settings validation if copied as is. Either set it to `local` or set `env_ignore_empty=True` in Settings.
- `ragdocs.pipelines.base.run()` does not forward `run_metadata`; M08 will likely need it.
- `list_runs()` calls the deprecated `POST /runs/query` (removed 2027-01-31, see "LangSmith deprecation notice" above); M09 experiment upload and any run read-back must use `client.runs.query()` and follow https://docs.langchain.com/langsmith/smithdb-sdk-migration-query-runs#runs-query.

Prerequisites for the next module
- LangSmith key in .env; `LANGSMITH_TRACING` recorded in each eval run's config.json (D18).
- `stream(question, run_metadata=...)` is available for tagging eval runs.
