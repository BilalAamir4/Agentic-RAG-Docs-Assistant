M08: Eval harness, custom judge, baseline run
Status: Partial
Date: 2026-11-16

Goal
`py tasks.py eval --pipeline baseline` runs all 50 items, throttled and resumable, and records the full PipelineResult, token usage, LangSmith run id and deterministic scores. Per the human's change (D9 update), judging is a separate resumable pass, `py tasks.py judge --run-dir DIR`, writing judge_v<N>.jsonl. The judge is audited by hand on 10 items.

Current state (2026-11-16): harness, judge, report, compare, audit and tests are built; lint and tests pass. Baseline run results/runs/baseline-20261116-0919 is complete (50 lines) and judged (judge_v1.jsonl, 41 lines). Screenshot saved. results/judge_audit.md is written and waits for the human columns. Pending: audit score and gate (D9), commit.

What was built
- src/ragdocs/providers/usage.py: TokenUsage callback handler; per-model input/output tokens and calls, keyed by `ls_model_name`; calls without usage data counted in usage_missing, including failed calls (on_llm_error, added after the baseline run, see Known issues). Runtime-safe.
- src/ragdocs/schemas.py: ModelTokenUsage, TokenUsageRecord, JudgeVerdict (rationale truncated to 60 words), ItemScores (JSON aliases context_hit@5, context_evidence_recall@5), EvalRecord (per_question line), JudgeRecord (judge_v<N> line), JUDGE_RATIONALE_MAX_WORDS.
- src/ragdocs/io_utils.py: append_jsonl, read_json, write_json.
- src/ragdocs/config.py: judge_model = gemini-3.5-flash-lite, judge_prompt_version = 1, groq_tpm_limit 8000, groq_rpm_limit 30, groq_rpd_limit and groq_tpd_limit maps (1000 RPD, 200000 TPD per gpt-oss model), groq_quota_timezone UTC, judge_tpm_limit 250000, judge_rpm_limit 15, judge_rpd_limit 500, judge_quota_timezone America/Los_Angeles, throttle_safety 0.9, throttle_window_s 60, eval_initial_token_estimate 3000, eval_context_k 5, eval_item_attempts 2, eval_audit_seed 21, eval_audit_strata, eval_set_sha256, eval_set_tag.
- src/ragdocs/pipelines/base.py, baseline.py: `stream(question, run_metadata=None, callbacks=None)`; callbacks appended after CallCounter in the generate call config.
- src/ragdocs/eval/throttle.py: RollingBudget (trailing-minute TPM/RPM; daily RPD and TPD at 0.9 x limit over a rolling 24 h (Groq) or calendar day (Gemini); resets_at walks events for rolling windows), BudgetStore (cache/budget.json v2: timestamped events per model, 2-day retention, v1 migration), DailyLimitReached, UsageEstimator, groq_budgets, judge_budget, embedding_budget, all_budgets, default_store, wait_all.
- src/ragdocs/eval/budget_recorder.py: BudgetRecorder and install_budget_recorder (LangChain configure hook plus embedding usage listener; every live call written to cache/budget.json).
- src/ragdocs/providers/embeddings.py: GeminiEmbedder notifies usage listeners on every API attempt (estimate_embed_tokens); no behaviour change without a listener.
- scripts/budget.py and `py tasks.py budget`: per-model window usage and remaining quota; --need check.
- scripts/structured_output_check.py: function_calling vs json_schema strict on 10 eval questions (D23).
- tests/test_budget.py: rolling window, resets_at, v2 store, legacy migration, recorder via configure hook and listener.
- src/ragdocs/eval/prompts.py: JUDGE_PROMPT (definitions verbatim, claim-listing instruction, structured fields only), JUDGE_USER_TEMPLATE, JUDGE_EXCERPT_TEMPLATE.
- src/ragdocs/eval/judge.py: judge_item, build_judge_messages (excerpts numbered in context order, CITED / NOT CITED from structured citations), judge_cache_key (sha1 of judge_model, judge_prompt_version, question, answer text, ordered excerpt texts, cited flags), diskcache in cache/judge, load_records.
- src/ragdocs/eval/judge_run.py: run_judge; resumable, budgeted, traced as `judge_item`, 2 attempts per item, exit 3 at the daily cap or after repeated failures; writes judge_v<N>.jsonl and rewrites the summary; never modifies per_question.jsonl.
- src/ragdocs/eval/scoring.py: must_mention_coverage, score_item, judge_eligible, latest_judge_file, effective_verdicts (highest judge_v<N>.jsonl, else per_question.jsonl).
- src/ragdocs/eval/runner.py: run_eval; configure_tracing at start; eval-set sha256 and `git diff --quiet eval-set-v1 -- data/eval/eval_set.jsonl` checks; config.json written first (or checked on resume); items in id order; one `eval_item` trace per item; one appended line per item; resume by id; exit 3 with remaining ids and reset time; flush_traces in finally.
- src/ragdocs/eval/report.py: summarize (with optional extra score files for M09), render_markdown, write_summary, format_rate "rate (count/n)".
- src/ragdocs/eval/compare.py: render_comparison, check_comparable, changed_questions.
- src/ragdocs/eval/judge_audit.py: select_audit_items, write_audit (refuses to overwrite filled labels), parse_audit_table, score_audit.
- scripts/run_eval.py, scripts/judge_run.py, scripts/compare_runs.py, scripts/judge_audit.py: thin CLIs.
- tasks.py: eval --pipeline NAME [--run-dir DIR], judge --run-dir DIR, judge-audit --run-dir DIR [--score], compare RUN_DIR...; other commands unchanged.
- requirements-dev.txt: pinned tzdata==2026.5 (zoneinfo on Windows needs it; already installed as a pandas dependency).
- tests/eval_fakes.py, tests/test_eval_throttle_usage.py, tests/test_eval_runner.py, tests/test_eval_report.py: new. tests/test_baseline_snapshot.py: callbacks test added. tests/test_import_boundaries.py: usage module boundary test. tests/test_config.py: judge_model default updated.
- docs/screenshots/langsmith-eval-item.png: q001 eval_item trace (1568 x 736), captured with Claude in Chrome on 2026-11-16.
- results/runs/baseline-20261116-0919/: config.json, per_question.jsonl (50 lines), judge_v1.jsonl (41 lines), summary.json, summary.md.
- results/judge_audit.md: 10-item audit sheet, human columns empty.
- docs/DECISIONS.md: D7 updates (judge model by budget, Groq TPD budget), D9 updates (judging decoupled, judge definition, audit gate pending).

How to run
- `py tasks.py eval --pipeline baseline` (prints the run dir; on exit code 3 re-run with `--run-dir <that dir>`).
- `py tasks.py judge --run-dir results/runs/<run>` (on exit code 3 re-run the same command after the reset it prints).
- `py tasks.py judge-audit --run-dir results/runs/<run>`, fill the human columns in results/judge_audit.md, then `py tasks.py judge-audit --run-dir results/runs/<run> --score`.
- `py tasks.py compare results/runs/<a> results/runs/<b>` writes results/summary.md.

Verification

Step 1a: judge model and free-tier limits
- https://ai.google.dev/gemini-api/docs/rate-limits now redirects (301) to https://aistudio.google.com/docs/rate-limits, which lists no per-model free-tier numbers: "Rate limits depend on a variety of factors (such as your usage tier) and can be viewed in Google AI Studio." It also says "Requests per day (RPD) quotas reset at midnight Pacific time."
- Models: https://aistudio.google.com/docs/models lists gemini-3.8-flash, gemini-3.6-flash, gemini-3.5-flash-lite and gemini-3.1-flash-lite as Stable; gemini-2.5-flash-lite "not deprecated"; gemini-2.5-flash deprecated (routes to 3.5 Flash-Lite from 2026-12-01).
- Pricing: https://aistudio.google.com/docs/pricing shows "Free of charge" free-tier input/output for Gemini 3.6 Flash and 3.5 Flash-Lite.
- Structured output: langchain-google-genai 4.4.1 .venv\Lib\site-packages\langchain_google_genai\data\_profiles.py has `"structured_output": True` for gemini-2.5-flash-lite, gemini-3.1-flash-lite, gemini-3.5-flash-lite and gemini-3.6-flash; there is no gemini-3.8-flash profile.
- Free-tier numbers read by the human from the AI Studio project page (RPM / TPM / RPD): gemini-3.6-flash 5 / 250K / 20; 2.5 Flash-Lite 10 / 250K / 20; 3.1 Flash-Lite 15 / 250K / 500; 3.5 Flash-Lite 15 / 250K / 500.
- gemini-3.6-flash (first pick) tripped the "more than 2 days of judge quota" stop rule; the human set a budget rule (D7 update) and chose gemini-3.5-flash-lite.
- Live check (2026-11-15): `ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite").with_structured_output(<pydantic model>)` returned a valid object; TokenUsage recorded 27 in / 23 out, usage_missing 0. langchain-google-genai warns "Model 'gemini-3.5-flash-lite' uses fixed sampling defaults; the sampling parameter(s) temperature will be ignored."

Groq limits
- https://console.groq.com/docs/rate-limits: "the limits shown below are the base limits for the Developer plan"; rows openai/gpt-oss-120b and openai/gpt-oss-20b "30 | 1K | 8K | 200K" (RPM, RPD, TPM, TPD). The Free-plan tab did not render.
- Free-plan values read by the human from the org limits page: gpt-oss-120b, gpt-oss-20b and qwen/qwen3.8-27b 30 RPM / 1K RPD / 8K TPM / 200K TPD; llama-3.3-70b-versatile not listed.
- Structured output support for Groq candidates: https://console.groq.com/docs/structured-outputs (json_schema: gpt-oss-20b, gpt-oss-120b, qwen/qwen3.8-27b, meta-models/muse-spark-open); https://console.groq.com/docs/tool-use (llama-3.3-70b-versatile supports tool use).

Step 1b: where token usage is exposed
- langchain-groq 1.1.3, langchain_groq\chat_models.py `_create_chat_result` (around line 780): `message.usage_metadata = _create_usage_metadata(token_usage)` from the response `usage`; `llm_output = {"token_usage": ..., "model_name": self.model_name, ...}`.
- langchain-google-genai 4.4.1, langchain_google_genai\chat_models.py `_response_to_result` (around lines 2040 to 2165): builds usage from `response.usage_metadata` (prompt, candidates, thoughts tokens) and sets `message.usage_metadata`; `model_name` in response_metadata is `response.model_version`.
- langchain-core 1.6.10, language_models\chat_models.py: for a single generation, `llm_output` is merged into `response_metadata` (around line 2042); `inheritable_metadata` includes `_get_ls_params_with_defaults` (`ls_model_name`) for callbacks (around line 1029). callbacks\usage.py UsageMetadataCallbackHandler reads `generations[0][0].message.usage_metadata` in on_llm_end, the same source TokenUsage uses.
- with_structured_output: the chat model runs as a step of a RunnableSequence; callbacks propagate to it, so on_llm_end gets the raw AIMessage.
- Live check (2026-11-15), Groq structured output through the real answer path (build_structured_llm + AnswerDraft, one stub excerpt, no embedding): valid AnswerDraft; TokenUsage recorded openai/gpt-oss-120b 400 in / 250 out, 1 call, usage_missing 0. Result: token usage is available for Groq structured-output calls.
- A first Groq probe with a toy prompt failed with `400 tool_use_failed` ("Tool choice is required, but model did not call a tool"). This can happen inside an eval item too; the runner retries an item once (eval_item_attempts = 2) before pausing with exit code 3.

Embedding quota (human question, 2026-11-15), corrected 2026-11-16
- The AI Studio rate-limit table I relied on is labelled "Peak usage per model compared to its limit over the last 28 days" (default time range 28 Days). The 977/1K RPD and 146/100 RPM for Gemini Embedding 1 are the peak day and peak minute in those 28 days, not usage on 2026-11-15. My earlier conclusion that about 966 requests came from another source that day was wrong; there is no evidence of use outside this project.
- Claude Code sessions in the 2026-11-15 Pacific day made at most 11 query embeddings (scripts\ask.py at 08:10:17Z and the M07 overhead script, 10 runs, at 08:12:16Z).
- 2026-11-16 about 09:20Z, AI Studio "1 Day" view (charts span 2026-11-15 02:00 to 2026-11-16 02:00 PST): Gemini Embedding 1 0/100 RPM, 0/30K TPM, 0/1K RPD; Gemini 3.5 Flash Lite 1/15 RPM (the live check), 27/250K TPM, 0/500 RPD. Gate (at least 50 embedding and 42 Flash Lite requests left) passed.

Tests and lint (2026-11-16, after the on_llm_error fix)
- `py tasks.py lint`: "All checks passed!", "111 files already formatted".
- `py tasks.py test`: "127 passed, 1 deselected in 4.79s". The M07 snapshot test passes unchanged.

Baseline run (2026-11-16, tracing on, LANGSMITH_PROJECT=ragdocs-local)
- Run dir: results/runs/baseline-20261116-0919. Started 09:19Z; four invocations (three resumes after exit code 3); finished about 10:00Z.
- All three pauses were "item failed after 2 attempts" with Groq `400 tool_use_failed` on the structured-output call, never a quota limit:
  - q015, first invocation: model called tool `answer_draft` (the request's tool is `AnswerDraft`).
  - q028, second invocation: model called tool `json`.
  - q028, third invocation: "Tool choice is required, but model did not call a tool".
  - Each item succeeded on a later resume. At least 6 Groq calls failed (3 pauses x 2 attempts); a single failure followed by a successful retry is not logged, so the true count may be higher.
- per_question.jsonl: 50 lines, 50 unique ids, id order; langsmith_run_id set on all 50; usage_missing 0.
- Judge pass: `py tasks.py judge --run-dir results/runs/baseline-20261116-0919`, one invocation, exit 0, 41/41 eligible items judged, 0 failures, 0 cached.
- Totals:
  - Generation (successful attempts): openai/gpt-oss-120b 91,874 tokens in, 18,524 out, 50 calls.
  - Judge: gemini-3.5-flash-lite 94,959 in, 2,629 out, 41 calls.
  - cache/budget.json after the run: gpt-oss-120b 50 requests / 110,398 tokens; gemini-3.5-flash-lite 41 requests / 97,588 tokens. The Groq count misses the failed calls (see Known issues).
  - Embedding requests: 50 (one per item; not budgeted by the harness).
- Consistency check: context_hit@5 34/42 equals M05 hybrid hit@5 34/42 (results/runs/retrieval-20261025/table.md).
- Items the judge scored below 2 / 1: q024 (0, 0), q025 (0, 0), q034 (1, 0). False abstention: q029.

summary.md (results/runs/baseline-20261116-0919/summary.md):

### Run summary: baseline-20261116-0919

Pipeline: baseline. Tracing enabled: True.
Judge: gemini-3.5-flash-lite, prompt version 1 (source judge_v1.jsonl), judged 41/41 eligible items.

Rates are shown as rate (count/n). Correctness uses n = every answerable item;
a false abstention counts as correctness 0.

#### Overall

| Field | Value |
|---|---|
| items | 50 |
| answerable n | 42 |
| correct (correctness = 2) | 0.905 (38/42) |
| correct or partial (correctness >= 1) | 0.929 (39/42) |
| mean correctness (0-2) | 1.833 (n=42) |
| citation_support (judged items) | 0.927 (38/41) |
| context_hit@5 (on contexts given to the generator) | 0.810 (34/42) |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.726 (n=42) |
| mean must_mention coverage | 0.929 (n=42) |
| false_abstention | 0.024 (1/42) |
| abstention_correct (unanswerable) | 1.000 (8/8) |
| hallucinated (unanswerable) | 0.000 (0/8) |
| mean llm_calls | 1.000 (n=50) |
| p50 latency_ms | 2016 ms |
| p95 latency_ms | 4085 ms |
| mean tokens per question | 2207.960 (n=50) |
| used_web | 0.000 (0/50) |

#### Per category

| Field | single | multi | version | unanswerable |
|---|---|---|---|---|
| items | 28 | 8 | 6 | 8 |
| answerable n | 28 | 8 | 6 | 0 |
| correct (correctness = 2) | 0.929 (26/28) | 0.750 (6/8) | 1.000 (6/6) | - |
| correct or partial (correctness >= 1) | 0.929 (26/28) | 0.875 (7/8) | 1.000 (6/6) | - |
| mean correctness (0-2) | 1.857 (n=28) | 1.625 (n=8) | 2.000 (n=6) | - |
| citation_support (judged items) | 0.929 (26/28) | 0.857 (6/7) | 1.000 (6/6) | - |
| context_hit@5 (on contexts given to the generator) | 0.786 (22/28) | 0.875 (7/8) | 0.833 (5/6) | - |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.786 (n=28) | 0.500 (n=8) | 0.750 (n=6) | - |
| mean must_mention coverage | 0.929 (n=28) | 0.875 (n=8) | 1.000 (n=6) | - |
| false_abstention | 0.000 (0/28) | 0.125 (1/8) | 0.000 (0/6) | - |
| abstention_correct (unanswerable) | - | - | - | 1.000 (8/8) |
| hallucinated (unanswerable) | - | - | - | 0.000 (0/8) |
| mean llm_calls | 1.000 (n=28) | 1.000 (n=8) | 1.000 (n=6) | 1.000 (n=8) |
| p50 latency_ms | 1958 ms | 2542 ms | 2500 ms | 1644 ms |
| p95 latency_ms | 8658 ms | 2883 ms | 2899 ms | 1977 ms |
| mean tokens per question | 2298.679 (n=28) | 2163.250 (n=8) | 2178.333 (n=6) | 1957.375 (n=8) |
| used_web | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.000 (0/8) |

#### Totals (generation)

- Tokens in: 91874; tokens out: 18524; LLM calls: 50; calls without usage data: 0
- openai/gpt-oss-120b: 91874 in, 18524 out, 50 calls
- Judge: 94959 in, 2629 out, 41 calls, 0 cached verdicts

LangSmith check (2026-11-16, Claude in Chrome)
- Project ragdocs-local, q001 eval_item trace: eval_item (1.88 s) > baseline (1.73 s) > hybrid_retrieve (0.64 s) and generate (1.09 s) > ChatGroq openai/gpt-oss-120b (1.777K tokens) and PydanticToolsParser. Saved docs/screenshots/langsmith-eval-item.png.
- docs/screenshots/langsmith-baseline-trace.png (M07) already exists (committed in 1ca68ef); not retaken.

Judge audit
- `py tasks.py judge-audit --run-dir results/runs/baseline-20261116-0919` wrote results/judge_audit.md with q006, q011, q015, q022, q024, q028 (single), q031, q033 (multi), q040, q041 (version). Score: pending human labels.

Decisions made
- Judge model and Groq TPD budget: see D7 updates.
- Judging decoupled from generation (human decision): see D9 update. per_question.jsonl keeps a `verdict` field that is always None; the verdict lives in judge_v<N>.jsonl.
- Daily quota windows per provider: Groq budgets use UTC dates (the prompt's choice; Groq's reset time is not documented on the pages read), the judge budget uses America/Los_Angeles because Google documents the RPD reset at midnight Pacific. The pause message prints the reset instant in UTC.
- Token estimate per model is the maximum observed per-item usage so far, seeded from lines already in the file on resume; 3,000 tokens and 1 request before any observation.
- An item that ends in an error event is retried once, then the run pauses with exit code 3 ("exhausted retries"). Usage of failed attempts is still recorded in the budgets.
- A run folder's config.json is written once; resuming checks pipeline, eval_set_sha256, index_manifest_hash, tracing_enabled and model_ids match and refuses otherwise.
- Correctness counts unjudged eligible items as missing (not 0); the summary marks judging incomplete and calls correctness a lower bound until the judge pass finishes.
- p50 and p95 latency use numpy.percentile (linear interpolation).

Deviations from the prompt
- Judge runs in a separate command (`judge --run-dir`), not inside eval, by the human's instruction. `--rejudge` is not a separate flag: after a version bump, `judge --run-dir` writes the new judge_v<N>.jsonl.
- judge_v<N>.jsonl lines carry judge_model, judge_prompt_version, usage and cached in addition to {id, verdict}.
- per_question lines add `judge_eligible`.
- compare_runs also refuses runs whose effective judge model differs (the prompt lists four guard fields; a different judge model makes correctness incomparable in the same way).
- judge-audit takes `--force` to overwrite an audit file that already has human labels; without it the command refuses.
- RollingBudget takes an optional tokens_per_day and a time zone (human-approved TPD budget; time zone per provider as above).
- tzdata pinned in requirements-dev.txt.

Known issues and limitations
- Groq structured-output failures: gpt-oss-120b sometimes calls a wrongly named tool or no tool (`400 tool_use_failed`); at least 6 failed calls in this run. Users of the baseline pipeline would see an error event in those cases. The eval scores the attempt that succeeded, so this failure rate does not appear in summary.md. The pipeline was not changed (module constraint).
- Failed calls were not counted in budgets during this run: TokenUsage counted only on_llm_end, so failed requests did not reach cache/budget.json. Fixed after the run by counting on_llm_error as a call with usage_missing (test added). The stored per-item records are unaffected because each record holds only its successful attempt's usage.
- ChatGroq retries (max_retries=3) inside one call are not visible to callbacks, so request counts can understate real requests.
- Daily counts in cache/budget.json cover only calls made by this harness; other use of the same Google project or Groq org (see the embedding quota note) is invisible to it.
- The embedding API is not budgeted by the harness; each item makes one live query embedding (`get_retriever` uses an uncached GeminiEmbedder).
- gemini-3.5-flash-lite ignores temperature=0 (fixed sampling); verdicts are cached, so a re-run with the same inputs returns the same verdict, but a cache-cleared re-judge may differ.

Structured-output fix and rerun (2026-11-16, in progress)
- Method check: scripts/structured_output_check.py on q015, q028, q001 to q008 (same contexts, one call per method): function_calling 2/10 failed, json_schema strict 0/10. Switched to json_schema strict (D23).
- Added structured_output_failures and rate_limited_attempts per item (from <run>/failed_attempts.jsonl) and both rows in summary.md.
- Rerun results/runs/baseline-20261116-1050 started 10:50Z (old run folder untouched). Paused at 16/50 at 11:01Z on Groq 429 "tokens per day (TPD): Limit 200000, Used 197584". structured_output_failures so far: 0 over 16 items; rate_limited_attempts 4 (q016); q017 has 6 logged 429 attempts.
- Why the harness did not stop first: RollingBudget._check_daily compared against the full daily limits, not safety x limit; and cache/budget.json (193,290 tokens) is below Groq's count (about 199,800) because failed calls before the on_llm_error fix were not recorded. Fixed: daily checks now use safety x limit (test added). Tests: "130 passed, 1 deselected".
- Groq's TPD is not a UTC calendar day: all ten 429 retry-after values equal (used + requested - 200,000) / (200,000 / 86,400 s), a token bucket refilling at about 2.31 tokens/s (D7).

Budget model and recorder (human decisions, 2026-11-16, D7)
- First switched the Groq budget to a rolling 24-hour window, then (human, option 2) to a draining bucket: balance = recorded usage drained at limit / 86,400 s (tokens 2.315/s, requests 0.0116/s), available = 0.9 x limit - balance. Basis: the ten 429 retry-after values match this formula to 0.1 s (table in D7).
- 429 backstop in the eval runner: wait for Groq's retry-after (pause if over 1,800 s or after 3 waits per item); a per-day 429 while the model predicted room is a model miss (cache/budget_model_misses.jsonl); at 2 misses the run pauses and the Groq window goes back to rolling_24h.
- Every live Groq or Gemini call is recorded through ragdocs.eval.budget_recorder (LangChain configure hook for chat models, usage listener for GeminiEmbedder), installed by the eval and judge runners, ask.py, build_index.py, eval_retrieval.py, structured_output_check.py and live tests.
- New command `py tasks.py budget [--need MODEL=TOKENS[:REQUESTS]]`. AGENTS.md hard rule "API budget" added.
- cache/budget.json rebuilt for 2026-11-16 from run evidence (earlier files kept outside the repo): gpt-oss-120b 102 requests, 1 reconciliation event of 18,730 tokens at 11:01:26Z so the bucket balance equals Groq's Used 197,585 then; gemini-3.5-flash-lite 41 / 97,588; gemini-embedding-001 92 requests.
- `py tasks.py budget --need openai/gpt-oss-120b=110000:34` (2026-11-16 about 11:55Z): balance 193,240, "DOES NOT FIT; fits at 2026-11-17T02:22+00:00", exit 1.
- Tests: `py tasks.py lint` "All checks passed!", "119 files already formatted"; `py tasks.py test` "143 passed, 1 deselected in 4.64s".

Model misses (bucket model)
- None so far.

Open questions for the human
- None pending. Next session (after 02:22Z on 2026-11-17): budget check for openai/gpt-oss-120b=110000:34, resume results/runs/baseline-20261116-1050 if it fits, judge, write the correctness-2 / context_hit@5-0 list, regenerate results/judge_audit.md, stop for the human labels.

Proposed follow-ups (out of scope)
- Cache query embeddings at runtime (or in the eval only) so resumed or repeated runs do not re-embed; this touches retrieval, so it needs a decision.
- `.env.example` has `RAGDOCS_ENV=` empty (carried over from M07).
- Groq tool_use_failed: try `with_structured_output(AnswerDraft, method="json_schema", strict=True)` for gpt-oss models (Groq lists gpt-oss-120b under strict json_schema at https://console.groq.com/docs/structured-outputs; langchain-groq 1.1.3 `_STRICT_STRUCTURED_OUTPUT_MODELS`). This changes the pipeline, so it needs its own module and a re-run.
- Cohere rerank calls are not recorded in cache/budget.json. Not needed now: use_reranker is False, so nothing calls Cohere. Add recording if reranking is turned on.

Prerequisites for the next module
- results/summary.md written by `py tasks.py compare results/runs/baseline-20261116-0919` (single-run table).
- Pending: audit gate result in D9; commit "M08: eval harness, judge and baseline run" (run folder, results/judge_audit.md, results/summary.md).
