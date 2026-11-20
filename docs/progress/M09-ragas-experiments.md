M09: RAGAS scoring, LangSmith experiments, baseline freeze
Status: Done
Date: 2026-11-20

Goal
Score the stored baseline run (results/runs/baseline-20261116-1050) with RAGAS faithfulness, response relevancy, context precision (with reference) and context recall, upload it to LangSmith as an experiment on dataset ragdocs-eval-set-v1, extend compare with RAGAS rows and a paired view, and tag v1-baseline. No answers are regenerated.

Module prompt: "M09. RAGAS scoring, LangSmith experiments, baseline freeze" from the plan file "RAG Portfolio Vercel Build Plan and Antigravity Module Prompts.md" (human's copy, outside the repo), with the human's path A instructions of 2026-11-18.

What was built
- requirements-ragas.txt: 105 pinned packages for .venv-ragas (resolved in a clean Python 3.12 venv from ragas==0.4.4, langchain-google-genai, diskcache).
- .gitignore: .venv-ragas/.
- tasks.py: `ragas-setup` (creates .venv-ragas from requirements-ragas.txt; needs `py -3.12`), `ragas --run-dir DIR [--out-dir DIR] [--ids ...] [--plan-only]`.
- src/ragdocs/config.py: ragas_llm_model gemini-3.1-flash-lite, ragas_llm_rpm/tpm/rpd_limit 15/250000/500, ragas_llm_quota_timezone, ragas_embedding_model (None = embedding_model), ragas_response_relevancy_strictness 3, ragas_max_attempts 3, ragas_timeout_s 180, ragas_llm_calls_per_metric and ragas_embedding_requests_per_metric (measured), ragas_tokens_per_llm_call 2500, ragas_venv_dir.
- src/ragdocs/eval/throttle.py: ragas_llm_budget; all_budgets includes the RAGAS LLM, so `py tasks.py budget` shows it.
- src/ragdocs/eval/ragas_export.py: eligibility (D19 population rules), to_ragas_row, build_ragas_input, export_ragas_input (never overwrites a different existing file), ragas_python, ragas_tool_args, ragas_tool_env.
- scripts/export_ragas_input.py: thin CLI for the export.
- scripts/ragas_run.py: export, then run tools/ragas_score.py in .venv-ragas with Settings-derived arguments; GOOGLE_API_KEY (via Settings.require) only in the child environment; LANGSMITH_* and LANGCHAIN_* variables removed.
- tools/ragas_budget.py: standard-library BudgetFile (D24 contract) and CalendarBudget (per-minute throttle, calendar-day cap at limit x safety, DailyLimitReached).
- tools/ragas_score.py: standalone scorer (see Step 2 for the API); diskcache in cache/ragas for metric results and embeddings; budget plan; exit code 3 on a daily cap or a provider quota error.
- tests/test_ragas_export.py: projection fields and order, eligibility flags, no-context rule, export idempotence, tool arguments and environment, budget file contract (byte-identical files from both writers, cross-reads), daily cap parity with RollingBudget, tool summary, cache key stability and budget plan arithmetic.
- tests/test_import_boundaries.py: `ragas` added to the prefixes ragdocs.api.app must not import.
- docs/DECISIONS.md: D19 update (gate failure, path A, API choice), D24 budget file contract.

How to run
- `py -3.12 tasks.py ragas-setup` once.
- `py tasks.py ragas --run-dir results/runs/<run> --plan-only` prints the budget plan.
- `py tasks.py ragas --run-dir results/runs/<run>` scores and writes the three files into the run folder; on exit code 3 rerun the same command after the reset it prints.

Verification

Step 1: dependency gate (2026-11-18)
- Latest stable ragas: 0.4.4, uploaded to PyPI 2026-11-14T03:08:42Z, requires_python ">=3.9" (https://pypi.org/pypi/ragas/json). The project venv is Python 3.12.9. Earlier releases: 0.4.3 (2026-01-13), 0.4.4rc1 (2026-11-13, pre-release).
- `.venv\Scripts\python -m pip install --dry-run --report cache\ragas-dryrun.json ragas==0.4.4`: exit 0; 38 packages would be installed.
- Parsed against every `==` line in requirements.txt and requirements-dev.txt:
  - tenacity 9.1.4 -> 8.5.0 (pinned in requirements.txt)
  - langchain-core 1.6.10 -> 1.8.2 (pinned in requirements.txt)
  - langsmith 0.14.7 -> 0.15.0 (pinned in requirements.txt)
  - also changed, not pinned: certifi 2026.7.22 -> 2026.10.23, langchain-protocol 0.0.19 -> 0.0.21
  - torch, transformers, sentence-transformers: not installed.
- Gate result: FAIL. Extra check: with every pin as a constraint (cache\ragas-dryrun-constrained.json) pip resolves by backtracking to instructor 0.4.8, typer 0.9.4, docstring-parser 0.15 and langchain 1.4.6; not used.
- Human decision: path A (isolated venv), recorded in D19.
- .venv-ragas: built once by hand to resolve, then deleted and rebuilt with `py -3.12 tasks.py ragas-setup` (exit 0); its `pip freeze` is identical to requirements-ragas.txt. No torch or transformers in it. Notable packages: langchain-core 1.8.2, langchain-google-genai 4.5.0, langchain-community 0.4.2, openai 1.109.1, instructor 1.3.2, datasets 5.2.0, pyarrow 26.0.1, scipy 1.18.1, scikit-network 0.33.5.
- requirements.txt and requirements-dev.txt: `git diff --stat` empty. `py tasks.py bundle-check`: "Total bundle size: 229.75 MB (limit: 400.00 MB)", exit 0.

Step 2: installed RAGAS API (.venv-ragas\Lib\site-packages\ragas, version 0.4.4)
- Two metric APIs exist. ragas\metrics\__init__.py: importing metric classes from ragas.metrics "is deprecated and will be removed in v1.0" (lines 225 to 244); the replacement is ragas.metrics.collections.
- ragas\metrics\collections\base.py `_validate_llm` requires InstructorBaseRagasLLM. ragas\llms\base.py `_get_instructor_client` uses `instructor.from_genai` for the google-genai SDK; instructor 1.3.2 (instructor\__init__.py) has only `from_gemini` (old google-generativeai SDK). `llm_factory` auto-selects the LiteLLM adapter for Gemini, and litellm is not installed. So the collections API cannot drive Gemini in this environment.
- Chosen: legacy single-turn metrics with LangChain wrappers (ragas\llms\base.py LangchainLLMWrapper line 142, ragas\embeddings\base.py LangchainEmbeddingsWrapper line 260; both warn they are deprecated).
- Metric classes and needs (ragas\metrics\_*.py `_required_columns`):
  - Faithfulness: LLM; user_input, response, retrieved_contexts.
  - ResponseRelevancy: LLM and embeddings; user_input, response; strictness 3 (number of generated questions).
  - LLMContextPrecisionWithReference: LLM; user_input, retrieved_contexts, reference.
  - LLMContextRecall: LLM; user_input, retrieved_contexts, reference.
- Sample fields: ragas.dataset_schema.SingleTurnSample(user_input, response, retrieved_contexts, reference), as expected.
- Sync scoring: `metric.single_turn_score(sample, callbacks=None)` (ragas\metrics\base.py line 412) runs the async scorer; exceptions propagate to the caller; a metric with nothing to judge returns float NaN (for example Faithfulness with no statements).
- Retries: LangchainLLMWrapper wraps calls in tenacity with RunConfig (ragas\run_config.py: timeout 180, max_retries 10, max_wait 60 by default; stop_after_attempt(max_retries)). The tool sets RunConfig(max_retries=3, timeout=180) and ChatGoogleGenerativeAI(max_retries=0), so every attempt goes through LangChain callbacks and is recorded. ragas also re-prompts on unparseable output (ragas\prompt\pydantic_prompt.py retries_left=3).
- n > 1: ResponseRelevancy asks for `strictness` completions. The async path passes n to any LangChain model with an `n` attribute (ragas\llms\base.py line 308); Gemini rejected it: "Multiple candidates is not enabled for this model" (400 INVALID_ARGUMENT, first smoke run). Fixed with LangchainLLMWrapper(bypass_n=True), which sends the prompt n times.
- Caching: ragas has ragas.cache.DiskCacheBackend and a `cacher` decorator for the collections LLMs; the tool uses its own diskcache (cache/ragas) for metric results (key: sha1 of ragas version, metric, LLM model, embedding model, user_input, response, retrieved_contexts, reference) and for embeddings (key: model and text).
- Telemetry: ragas\_analytics.py `do_not_track()` is true when RAGAS_DO_NOT_TRACK is "true"; the tool sets it, LANGSMITH_TRACING=false and LANGCHAIN_TRACING_V2=false before any import. Offline wiring check in .venv-ragas: "ragas 0.4.4 do_not_track True LANGSMITH_TRACING false"; chat model max_retries 0, RunConfig max_retries 3.
- Calls per metric, measured on q001 and q002 (counted with a LangChain callback on the chat model and by wrapping GoogleGenerativeAIEmbeddings.client.models.embed_content; retries included):

  | metric | q001 LLM calls | q002 LLM calls | embedding requests per item | texts per request |
  |---|---|---|---|---|
  | faithfulness | 2 | 2 | 0 | - |
  | response_relevancy | 3 | 6 | 2 | 1.75 (7 texts / 4 requests) |
  | context_precision | 5 | 7 | 0 | - |
  | context_recall | 1 | 2 | 0 | - |

  Faithfulness is statement generation plus one NLI call; context precision is one call per context (5 contexts); response relevancy is one call per generated question plus retries, then one embed_query and one embed_documents request. Settings use the means rounded up: 2, 5, 6, 2 LLM calls and 2 embedding requests.

Step 3: scorer smoke run (2 items, .venv-ragas)
- `py tasks.py budget --need gemini-3.1-flash-lite=60000:22 --need gemini-embedding-001=400:4`: both "fits" (0/500, 0/1000 used).
- First run (`py tasks.py ragas --run-dir results/runs/baseline-20261116-1050 --ids q001,q002 --out-dir cache/ragas-smoke`), exit 0, about 17 minutes: q001 faithfulness 0.6, context_precision 0.8875, context_recall 1.0; response_relevancy errored ("Multiple candidates is not enabled for this model"); q002 three metrics errored with "ClientConnectorDNSError: Cannot connect to host generativelanguage.googleapis.com:443 ... [getaddrinfo failed]" (local network outage, 11:56 to 12:12Z). 22 LLM requests recorded in cache/budget.json (failed attempts as 0 tokens).
- Fix: bypass_n=True (above). DNS resolved again (nslookup).
- Second run (`--out-dir cache/ragas-smoke2`; the 4 cached results were not recomputed), exit 0:
  - "q001 (1/2) {'faithfulness': 0.6, 'response_relevancy': 0.8056874290817656, 'context_precision': 0.8874999999778125, 'context_recall': 1.0} errors=[]"
  - "q002 (2/2) {'faithfulness': 0.7692307692307693, 'response_relevancy': 0.8456020100270257, 'context_precision': 0.94999999997625, 'context_recall': 1.0} errors=[]"
  - "Wrote ragas_config.json, ragas_scores.jsonl, ragas_summary.json to cache/ragas-smoke2"
  - 15 LLM requests (4 failed attempts, retried) and 4 embedding requests recorded in cache/budget.json.
- Tests: `py tasks.py lint` "All checks passed!", "122 files already formatted" (exit 0); `py tasks.py test` "152 passed, 1 deselected in 6.79s".

Budget plan (full baseline run, `py tasks.py ragas --run-dir results/runs/baseline-20261116-1050 --plan-only`, 2026-11-18)
- "Gemini LLM (gemini-3.1-flash-lite): faithfulness 39 x 2 = 78; response_relevancy 39 x 5 = 195; context_precision 42 x 6 = 252; context_recall 42 x 2 = 84; total 609 requests; used today 37/500; cap at 0.9 = 450; days needed 2"
- "Gemini embeddings (gemini-embedding-001): response_relevancy 39 x 2 = 78; total 78 requests; used today 4/1000; cap at 0.9 = 900; days needed 1"
- "Days needed overall: 2" (stop rule: more than 3).
- Because the full need does not fit today, the AGENTS.md budget rule is applied per day: day 1 scores q001 to q029 (384 LLM and 48 embedding requests; `py tasks.py budget --need gemini-3.1-flash-lite=960000:384 --need gemini-embedding-001=2000:48`: both "fits") into cache/ragas-day1; day 2 runs the full command into the run folder, reusing the cache.

Cache reuse check (human request, 2026-11-18)
- Same directory: scripts/ragas_run.py always passes `--cache-dir` = Settings.cache_dir / "ragas" (src/ragdocs/eval/ragas_export.py ragas_tool_args); `--out-dir` changes only where the three output files are written. The day-1 run (`--out-dir cache/ragas-day1`) and the full run (no `--out-dir`, so the run folder) therefore use the same cache/ragas.
- Key fields: tools/ragas_score.py cache_key hashes exactly [ragas version, metric, LLM model, embedding model, user_input, response, retrieved_contexts, reference]; no path, output folder, id or date. Test: tests/test_ragas_export.py checks the key changes with the version, the metric and the response, and that cache_report gives the same hits with a different --out-dir.
- New flag `--cache-check` (tool, scripts/ragas_run.py, tasks.py): reads cache/ragas only, prints hits and misses per metric and the remaining LLM and embedding requests; it imports ragas for its version string but builds no model and makes no API call. Errored metrics are never cached, so they show as misses.

Day-1 run (2026-11-18, 15:06Z to 16:05Z): paused, stop rule hit
- Command: `py tasks.py ragas --run-dir results/runs/baseline-20261116-1050 --out-dir cache/ragas-day1 --ids q001,...,q029`. Exit 3 after q014: "Paused: Error calling model 'gemini-3.1-flash-lite' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED ... 'You exceeded your current quota, please check your plan and billing details ...'". The printed message was truncated before the quota id, so it is not known whether the per-minute or the daily quota was hit.
- cache/budget.json, gemini-3.1-flash-lite, Pacific day 2026-11-18: 227 requests (93 failed, 0 tokens), 189,848 tokens; this run 190 requests (76 failed). Peak 16 recorded events in one minute (16:03Z), above 15 RPM: the throttle waits once per item on the estimate, while ragas sends response_relevancy prompts concurrently and retries inside a metric.
- Per-metric errors over the attempted items q001 to q014 (error texts are not available: errors are not cached and outputs are written only at the end):
  - faithfulness 1/13 (8%): q012
  - response_relevancy 5/13 (38%): q009, q011, q012, q013, q014
  - context_precision 2/14 (14%): q008, q011
  - context_recall 1/14 (7%): q011
- Stop rule ("more than 10% of eligible items error on any metric"): FAIL for response_relevancy and context_precision. Stopped; human decision needed.
- Cache check after the pause (`py tasks.py ragas --run-dir results/runs/baseline-20261116-1050 --cache-check`, no API calls): "Cache check: 8/42 items fully cached"; faithfulness 13/39 cached, response_relevancy 9/39, context_precision 12/42, context_recall 13/42; "Still needed (estimate): 440 LLM requests, 60 embedding requests". Every metric scored without error on q001 to q014 is a hit; the errored ones are misses and would be retried.

Fixes after day 1 (human instructions, 2026-11-18; no API calls)
- Error log: every failed LLM or embedding attempt and every metric error is appended to cache/ragas_errors.jsonl with the full exception chain and the provider's code, status and details (quota id when present). Pauses also write cache/ragas_partial/<out-dir name>/ragas_scores.partial.jsonl and ragas_summary.partial.json.
- Concurrency: ragas RunConfig(max_workers=1) is set, but max_workers only limits ragas's Executor (evaluate()), not single_turn_score. What actually serialises requests: SequentialLLM (tools/ragas_score.py) overrides BaseRagasLLM.generate. ragas 0.4.4 with bypass_n sent `[prompt] * n` as one concurrent LangChain batch inside one tenacity retry, so one failed prompt resent all n. Now each of the n prompts is its own request with its own retry. Offline check with FakeListChatModel: callbacks ['start', 'end', 'start', 'end', 'start', 'end'].
- Throttle: every LLM request (on_chat_model_start) and every embedding request waits on the per-minute window, capped at Settings.ragas_rpm_ceiling = 12. The per-item check is now the daily cap only. Retries pass through the same callbacks, so they are throttled, recorded and logged.
- Estimates (Settings.ragas_llm_calls_per_metric): faithfulness 3, response_relevancy 6, context_precision 7, context_recall 2. These are day-1 means rounded up, with response_relevancy at its maximum.
- Tests: "169 passed, 1 deselected"; lint "All checks passed!".

Probe q009 (2026-11-18 16:16Z to 16:23Z)
- Budget before: gemini-3.1-flash-lite 227/500, 223 free under the 0.9 cap (rule: at least 40); embeddings 18/1000. `py tasks.py budget --need gemini-3.1-flash-lite=100000:40 --need gemini-embedding-001=400:2`: both "fits".
- Command: `py tasks.py ragas --run-dir results/runs/baseline-20261116-1050 --ids q009 --refresh --out-dir cache/ragas-probe-q009`, exit 0.
- Result: "q009 (1/1) {'faithfulness': 1.0, 'response_relevancy': 0.7427258146823407, 'context_precision': 0.999999999975, 'context_recall': 1.0} errors=[]". On day 1 q009 response_relevancy errored.
- Calls: 16 LLM requests (5 failed) and 2 embedding requests (3 texts). Per metric: faithfulness 4, response_relevancy 4, context_precision 7 (5 contexts), context_recall 1. Peak 9 requests in one minute.
- Every failed attempt (5, all retried successfully) was "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}" (google.genai ServerError, wrapped as GoogleAPIError). There were no 429s and no parse errors.
- response_relevancy and multiple generations: ResponseRelevancy asks for n = strictness = 3 generations per call (ragas/metrics/_answer_relevance.py line 143). ChatGoogleGenerativeAI accepts n, but gemini-3.1-flash-lite rejects it ("Multiple candidates is not enabled for this model", first smoke run), so bypass_n is required. With SequentialLLM those 3 generations are 3 sequential single requests.
- Reading (not proven for day 1, whose errors were not logged): the probe's only failures were transient 503 overload responses. Day 1's batch-of-3 retry made each 503 cost 3 requests and let a metric fail after 3 attempts. It also produced the per-minute bursts (16 per minute), which likely triggered the final 429. That 429's quota id was not captured, so per-minute versus per-day is still not established.

Full run (day 2: 2026-11-19 20:24Z to 20:56Z, Pacific day 2026-11-19)
- Before: usage 0/500 (LLM) and 0/1000 (embeddings). `py tasks.py ragas --run-dir results/runs/baseline-20261116-1050 --cache-check`: "Cache check: 9/42 items fully cached"; faithfulness 13/39 cached, response_relevancy 10/39, context_precision 12/42, context_recall 13/42; "Still needed (estimate): 520 LLM requests, 58 embedding requests". Plan: "total 729 requests; used today 0/500; cap at 0.9 = 450; days needed 2". `py tasks.py budget --need gemini-3.1-flash-lite=1125000:450 --need gemini-embedding-001=6000:58`: both "fits".
- `py tasks.py ragas --run-dir results/runs/baseline-20261116-1050`: exit 0 in one day; "Wrote ragas_config.json, ragas_scores.jsonl, ragas_summary.json to results/runs/baseline-20261116-1050". Actual use: 326 LLM requests (8 failed attempts, 423,291 tokens, peak 12 per minute) and 58 embedding requests (613 estimated tokens). That is fewer than the 520 estimated: the cache covered more, and there were few retries.
- RAGAS summary (ragas_summary.json):

  | metric | mean | n_eligible | n_scored | n_errored |
  |---|---|---|---|---|
  | faithfulness | 0.922 | 39 | 39 | 0 |
  | response_relevancy | 0.813 | 39 | 39 | 0 |
  | context_precision (on contexts given to the generator) | 0.720 | 42 | 42 | 0 |
  | context_recall (on contexts given to the generator) | 0.845 | 42 | 42 | 0 |

- 10% error rule (final failures after retries): 0/39, 0/39, 0/42, 0/42. PASS.
- Retried transient failures (cache/ragas_errors.jsonl since 20:24Z): 8 attempts, all "503 UNAVAILABLE" (ServerError), all retried successfully: context_precision 5, response_relevancy 2, faithfulness 1. No 429s.
- response_relevancy generations (cache/ragas_relevancy_generations.jsonl), first 3 items scored: q011, q012 and q013 each had 2 distinct questions out of 3 (one question repeated, one reworded), so the 3 generations are not identical. Over the 29 items logged, 7 had 3 identical questions. No setting changed.

Step 4 sanity check (11 audited items): FAIL, stopped
- Per item, human faithful label and RAGAS faithfulness:

  | id | human faithful | RAGAS faithfulness |
  |---|---|---|
  | q006 | yes | 0.500 |
  | q012 | yes | 1.000 |
  | q016 | no | 1.000 |
  | q023 | yes | 1.000 |
  | q024 | no | 0.889 |
  | q026 | yes | 1.000 |
  | q028 | yes | 0.667 |
  | q031 | yes | 1.000 |
  | q033 | no | 1.000 |
  | q040 | yes | 1.000 |
  | q041 | yes | 1.000 |

- Mean: yes 0.896 (n = 8), no 0.963 (n = 3). Expected yes > no; observed no > yes. Not every item has the same score. Per the module prompt, stopped before the experiment upload, compare, commit and tag.
- Observations, not yet investigated (needs a decision; ragas statement decompositions are not stored, so finding out why would need new LLM calls): RAGAS gave 1.0 to q016 (invented final code line) and q033 (claim not in any excerpt), and 0.889 to q024 (cause stitched from unrelated excerpts). It gave 0.5 to q006 and 0.667 to q028, both of which the human labelled faithful.

Faithfulness audit (human option 1, 2026-11-19 21:41Z)
- Budget: 326/500 used; `py tasks.py budget --need gemini-3.1-flash-lite=112500:45`: "fits". Command: `py tasks.py ragas --run-dir results/runs/baseline-20261116-1050 --ids q006,q012,q016,q023,q024,q026,q028,q031,q033,q040,q041 --faithfulness-audit`, exit 0. It runs ragas Faithfulness's own two steps (_create_statements, _create_verdicts, _compute_score) and writes results/runs/baseline-20261116-1050/ragas_faithfulness_audit.jsonl. That is a new file with, per item: the response, the exact retrieved_contexts, the joined NLI context, the statements, the verdicts with reasons, the score and the LLM calls. The scores and cache are untouched. 2 LLM calls per item (22 in all).
- Rescored values equal the stored ones on all 11 items (q006 0.5, q016 1.0, q024 0.889, q028 0.667, q033 1.0, the rest 1.0).
- (a) Code blocks:
  - q016: the code block produced 3 descriptive statements ("The provided Python code demonstrates the initialization of an InMemoryStore with an embedding index", "... the storage of memories ...", "... the retrieval of memories using semantic similarity ..."), all verdict 1. The invented line `print(items.value["text"]) # → "I love pizza"` (store.search returns a list) produced no statement.
  - q033: the code block produced no statement of its own; all 10 statements come from the prose.
  - q006, q024, q028: no code blocks.
- (b) Low scores:
  - q006 (0.5, 2 of 4 statements verdict 0):
    - Statement-generation paraphrase: the answer says "edit the thread's state", and the generated statement reads "allows an operator to overwrite state attributes on an existing thread". Verdict 0; the reason cites reducers accumulating rather than overwriting.
    - "performs these actions without running any node" got verdict 0, reason "does not explicitly state that the method performs these actions without running any node".
  - q028 (0.667): "Pregel uses the LastValue channel by default" got verdict 0, reason "states that LastValue is the default channel type, but it does not explicitly state that Pregel uses it by default". The other two statements got verdict 1.
  - For the human "no" items:
    - q024 (0.889): only "The conflict causes the parallel branch to fail" got verdict 0. The stitched cause got verdict 1 statement by statement.
    - q033 (1.0): "The root stream outputs the tokens of the parent agent" got verdict 1 by inference ("implying the parent graph itself emits its own tokens"), which is the claim the human found in no excerpt.
- (c) Contexts:
  - For all 11 audited items, retrieved_contexts equals per_question context_texts exactly. Each string equals the chunk text in data/processed/chunks.jsonl, code fences are balanced (2 to 5 of the 5 contexts per item contain code), and the NLI context is exactly their "\n" join.
  - For all 50 rows of ragas_input.jsonl, retrieved_contexts and response equal the stored context_texts and answer text (0 mismatches).
  - The contexts are not truncated by our code; ragas passes them whole.
- Decision path: contexts passed correctly, so no setup bug; option 2 (D19).

Step 5: LangSmith dataset and experiment
- Verified in langsmith 0.14.7 (.venv\Lib\site-packages\langsmith):
  - client.py: has_dataset, read_dataset, create_dataset (5831), create_examples (7019; dicts with inputs, outputs, metadata), list_examples (7396), create_project (5341, reference_dataset_id).
  - evaluation/_runner.py: evaluate (137) with `experiment=` an existing TracerSession keeps its exact name (1285), while a string gets a random suffix (1283). Evaluators returning {"results": [{"key", "score"}]} become feedback keys. The comparison URL is <base>/datasets/<dataset id>/compare?selectedSessions=<experiment id> (1372).
- How replay works: the target returns the stored outputs (answer, abstained, cited chunk ids, original langsmith_run_id) and the evaluator returns the stored scores. No model is called; evaluate runs with max_concurrency 0.
- `py tasks.py ls-dataset` (2026-11-18): "Dataset ragdocs-eval-set-v1 created: 6f229f5d-8cff-45b9-840f-3ec576feb329" (50 examples; eval_set sha256 in the description). Second run: "verified (same 50 ids and sha256)", no duplicates.
- `py tasks.py experiment --run-dir results/runs/baseline-20261116-1050` (2026-11-19 21:45Z): experiment baseline-20261116-1050, 50 examples.
  - API check (read_project include_stats): 14 feedback keys, but correctness had n = 39, mean 1.974. The 3 falsely abstained answerable items had no verdict, so they were omitted. That disagrees with the report rule (abstained = 0).
  - Fixed in langsmith_sync.item_feedback, with a new test.
  - Uploaded again with `--replace`: baseline-20261116-1050-r1 (id 587a3e7e-0328-432d-b0d6-a9dbc8d7c990), now current in langsmith_experiment.json; the first upload stays as a non-current log entry and nothing was deleted.
- r1 stats: 14 keys. correctness n 42 mean 1.833 (= summary "mean correctness (0-2) 1.833 (n=42)"); faithfulness n 39 0.922; response_relevancy n 39 0.813; context_precision n 42 0.720; context_recall n 42 0.845; citation_support n 39; abstention_correct n 8; hallucinated n 8; context_hit_at_5, context_evidence_recall_at_5 and must_mention_coverage n 42; llm_calls, latency_ms and tokens n 50.
- run_count is 58 for r1 and 62 for the first upload, against 50 examples; the stats endpoint also counts some evaluator-side runs. The example and feedback counts above are the check.
- URL (current): https://smith.langchain.com/o/dc790a75-743f-467d-a940-18bb085de125/datasets/6f229f5d-8cff-45b9-840f-3ec576feb329/compare?selectedSessions=587a3e7e-0328-432d-b0d6-a9dbc8d7c990

Step 6: compare
- `py tasks.py compare results/runs/baseline-20261116-1050`: "Wrote .../results/summary.md". It shows the four RAGAS rows as "mean (n)": faithfulness (prose-level grounding signal) 0.922 (39), response_relevancy 0.813 (39), context_precision (on contexts given to the generator) 0.720 (42), context_recall (on contexts given to the generator) 0.845 (42). Per-category rows are included. The Paired section says "only one run given".
- Screenshot: not taken at first because the browser extension was not connected. It was saved on 2026-11-20 as docs/screenshots/langsmith-baseline-experiment.png: the comparison view of baseline-20261116-1050-r1, with page zoom set to 0.7 so that all feedback columns fit, rows 1-14 visible, and latency_ms and tokens each showing "50 received".

Final verification (2026-11-19)
- `py tasks.py lint`: "All checks passed!", "126 files already formatted" (exit 0).
- `py tasks.py test`: "170 passed, 1 deselected in 21.24s".
- requirements.txt and requirements-dev.txt unchanged. The existing run files (config.json, per_question.jsonl, judge_v1.jsonl, judge_v2.jsonl, failed_attempts.jsonl, summary.json, summary.md) are unmodified. New files in the run folder: ragas_input.jsonl, ragas_config.json, ragas_scores.jsonl, ragas_summary.json, ragas_faithfulness_audit.jsonl, langsmith_experiment.json.

Decisions made
- Path A and the legacy LangChain metric API (D19 update); budget file contract (D24).
- LangSmith correctness feedback uses the report rule (an abstained answerable item = 0), so LangSmith and summary.md agree.
- RAGAS faithfulness is presented as a prose-level grounding signal next to the judge (D19, human option 2 after the audit).
- Sequential requests, a 12 RPM ceiling before every call, and full error logging (D19 update, human instructions after day 1).
- Paired view in both directions and the presentation rule (human decision): the count-based correctness verdict is printed first in each Paired block as the primary result; the paired correctness row is supporting detail; must_mention coverage is labelled "soft signal, D15" in summary and compare tables. Recorded in D19 for the M15 README (there is no README.md yet; M15 creates it).
- Per-day subsets with --ids so each day's need passes the budget check before it runs.
- Smoke and partial outputs go to cache/ (gitignored); the run folder receives the three RAGAS files only from the complete run.

Deviations from the prompt
- The plan expected ragas installed in .venv and src/ragdocs/eval/ragas_score.py; the gate failed, so the human chose the isolated setup (tools/ragas_score.py).
- Response relevancy is scored with Gemini sending each of the 3 question prompts separately (bypass_n), the same number of questions.

Known issues and limitations
- google-genai's aiohttp layer prints "RuntimeWarning: coroutine 'ClientResponse.json' was never awaited" during runs; scores and recorded calls are unaffected.
- When one prompt of a multi-prompt LangChain call fails, on_llm_error fires for every prompt in the batch, so failed attempts can be over-counted (never under-counted) in cache/budget.json.
- Errored metrics are not cached, so a rerun retries them.

Open questions for the human
- Resolved (human, option 2 after the faithfulness audit): the Step 4 sanity check failed (yes 0.896, no 0.963). Contexts were passed correctly, so RAGAS faithfulness is kept as a prose-level grounding signal (D19).

Proposed follow-ups (out of scope)
- Move to ragas.metrics.collections when a resolved instructor provides from_genai (or with a LiteLLM client), before ragas 1.0 removes the legacy imports.

Prerequisites for the next module
- Tag v1-baseline (annotated, not pushed) freezes the baseline run, judge v2 verdicts and RAGAS scores; M10 and M11 compare against results/runs/baseline-20261116-1050 with `py tasks.py compare`.
- RAGAS for a new run: `py tasks.py ragas --run-dir DIR` (budget check and `--cache-check` first; it may need more than one day).
- LangSmith: `py tasks.py experiment --run-dir DIR` attaches a new run to dataset ragdocs-eval-set-v1.
