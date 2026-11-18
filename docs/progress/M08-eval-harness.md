M08: Eval harness, custom judge, baseline run
Status: Done
Date: 2026-11-18

Goal
`py tasks.py eval --pipeline baseline` runs all 50 items, throttled and resumable, and records the full PipelineResult, token usage, LangSmith run id and deterministic scores. Per the human's change (D9 update), judging is a separate resumable pass, `py tasks.py judge --run-dir DIR`, writing judge_v<N>.jsonl. The judge is audited by hand on 10 items.

Current state (2026-11-18): harness, judge, report, compare, audit and tests are built; lint and tests pass. The first baseline run results/runs/baseline-20261116-0919 (function_calling) is kept as evidence. The baseline run of record is results/runs/baseline-20261116-1050 (json_schema strict, D23): 50/50 items, judged 39/39 eligible items. Judge audit on 11 items passed the gate (10/11 on each column, D9). results/summary.md written by `py tasks.py compare results/runs/baseline-20261116-1050`.

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
- src/ragdocs/eval/judge_audit.py: select_audit_items, write_audit (refuses to overwrite filled labels), parse_audit_table, score_audit. 2026-11-17: select_low_score_items and AuditSelection (items with judge correctness below Settings.eval_audit_add_below_correctness added after the seeded draw, flagged in a new selection column); AuditScore.needed/passes for the gate (Settings.eval_audit_gate_rate); scripts/judge_audit.py prints the gate; test added in tests/test_eval_report.py.
- scripts/run_eval.py, scripts/judge_run.py, scripts/compare_runs.py, scripts/judge_audit.py: thin CLIs.
- tasks.py: eval --pipeline NAME [--run-dir DIR], judge --run-dir DIR, judge-audit --run-dir DIR [--score] [--force], compare RUN_DIR..., budget [--need ...]; other commands unchanged. (--force was accepted by scripts/judge_audit.py but not passed through by tasks.py until 2026-11-17.)
- pyproject.toml: `extend-exclude = ["results"]` for ruff (2026-11-17). ruff 0.17.0 formats Python code blocks inside Markdown, and the regenerated results/judge_audit.md quotes doc excerpts verbatim, so `py tasks.py lint` failed on a generated file and `py tasks.py format` would have rewritten it.
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
- First sheet (2026-11-16, run 0919, superseded, never labelled): q006, q011, q015, q022, q024, q028, q031, q033, q040, q041.
- Current sheet (2026-11-17): `py tasks.py judge-audit --run-dir results/runs/baseline-20261116-1050 --force` printed "Wrote .../results/judge_audit.md with items: q006, q012, q016, q023, q026, q028, q031, q033, q040, q041" (6 single, 2 multi, 2 version; seed 21). The draw differs from the first sheet because it samples from this run's judged items (q008 and q025 now abstain and are not judged). Judge verdicts on the 10: correctness 2 on all 10; citation_support 0 on q006, 1 on the other 9.
- Added item (human, 2026-11-17, D9 update): the draw contained no item the judge scored below 2, so every judged item with correctness below 2 is added, flagged "added: judge score < 2". This run has one: q024 (judge 1, 1). `py tasks.py judge-audit --run-dir results/runs/baseline-20261116-1050 --force` printed "seed 21: q006, q012, q016, q023, q026, q028, q031, q033, q040, q041" and "added (judge correctness < 2): q024". The table now has a selection column. Gate: at least 80% on each column over 11 items, so 9/11.
- Human labels (2026-11-18), entered into the three human columns of results/judge_audit.md (notes kept here so the cells stay parseable). Provenance per the human: Bilal labelled 8 items; Claude labelled all 11 independently; the 3 disagreements were resolved by reasoning item by item; the 3 items Bilal skipped use Claude's labels. Rules: a missing reference fact lowers correctness only if the question needs it; the structured CITED list is the citation (D20), inline [n] markers not required.

  | id | judge (corr, cite) | human corr | human cite | faithful | note |
  |---|---|---|---|---|---|
  | q006 | 2, 0 | 2 | 1 | yes | |
  | q012 | 2, 1 | 2 | 1 | yes | |
  | q016 | 2, 1 | 2 | 1 | no | invented final code line: items.value / "I love pizza" |
  | q023 | 2, 1 | 2 | 1 | yes | |
  | q026 | 2, 1 | 2 | 1 | yes | |
  | q028 | 2, 1 | 2 | 1 | yes | |
  | q031 | 2, 1 | 1 | 1 | yes | missing the different-schema pattern; the question needs it |
  | q033 | 2, 1 | 2 | 1 | no | "root stream still outputs the parent's tokens" is not in any excerpt |
  | q040 | 2, 1 | 2 | 1 | yes | |
  | q041 | 2, 1 | 2 | 1 | yes | |
  | q024 (added) | 1, 1 | 1 | 1 | no | cause stitched from unrelated excerpts [1] and [3]; reducer fix missing |

- `py tasks.py judge-audit --run-dir results/runs/baseline-20261116-1050 --score`:
  - "correctness agreement: 10/11"
  - "citation_support agreement: 10/11"
  - "gate (80% on each column, 9/11): PASS"
  - "disagreement q006: correctness judge 2 / human 2; citation_support judge 0 / human 1"
  - "disagreement q031: correctness judge 2 / human 1; citation_support judge 1 / human 1"
- Gate recorded in D9 (passed).
- Judge citation check (every judged item with citation_support 0, scratchpad script over both runs):
  - Run 1050: q006 only. Answer "Use the graph's `update_state` method ..." has no inline [n] markers; its structured CITED list holds excerpt [2]. Judge rationale: "it did not provide any citations from the excerpts, so citation_support is 0". The 0 is caused by the missing inline markers, which D20 does not require; the human label is 1.
  - Run 0919 (for comparison): q024 (inline [1][3]; rationale says the cited excerpts do not support the claim), q034 (inline [1][2] and [4]; rationale says [4] does not support the decorator usage), q025 (no inline markers; rationale only about the wrong ValidationError claim). None of these is marker-driven by its rationale.
  - So 1 of 39 judged items in the run of record (q006) is a marker-driven citation error.

Judge prompt v2 (human, 2026-11-18, D9 update)
- src/ragdocs/eval/prompts.py: JUDGE_PROMPT adds, under citation_support: "The CITED / NOT CITED flags on the excerpts are the answer's citations. Inline [n] markers in the answer text are optional: their presence, absence or placement must not affect citation_support." Nothing else in the rubric changed. src/ragdocs/config.py: judge_prompt_version = 2. tests/test_config.py expects 2; tests/eval_fakes.py pins version 1 for fixtures; tests/test_eval_runner.py bumps relative to the setting.
- Lint and test after the change: "All checks passed!", "115 files already formatted"; "144 passed, 1 deselected in 7.48s".
- `py tasks.py budget --need gemini-3.5-flash-lite=100000:39`: 0/500 requests used, "fits".
- `py tasks.py judge --run-dir results/runs/baseline-20261116-1050`: "Judge v2: 0 done, 39 to judge", "Judging complete", exit 0; 39 calls, 88,544 tokens (v1: 86,848). Answers not regenerated.
- v1 vs v2 verdicts: 39 ids in both; one change, q006 (2, 0) to (2, 1), v2 rationale "... supported by excerpt 2."
- `py tasks.py judge-audit --run-dir results/runs/baseline-20261116-1050 --score` with the unchanged human labels: "correctness agreement: 10/11", "citation_support agreement: 11/11", "gate (80% on each column, 9/11): PASS", "disagreement q031: correctness judge 2 / human 1; citation_support judge 1 / human 1".
- results/summary.md regenerated (`py tasks.py compare results/runs/baseline-20261116-1050`): judge prompt version 2; correct 0.905 (38/42); citation_support 1.000 (39/39).
- Known limitation: run 0919 keeps only judge_v1.jsonl; comparing it with run 1050 now fails the judge-version guard. It is evidence for D23, not a comparison base.

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
- 2026-11-17: ruff excludes results/ (pyproject.toml) and tasks.py passes judge-audit --force through; both were needed to run the requested `judge-audit --force` and keep `py tasks.py lint` passing without hand-editing a generated file.
- 2026-11-17: the eval budget check also listed gemini-embedding-001=400:34 (one query embedding per remaining item), per the AGENTS.md rule to check every model a run uses.

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
- Rerun results/runs/baseline-20261116-1050 started 10:50Z on 2026-11-16 (old run folder untouched); completed 2026-11-17 (see "Rerun completed" below). Paused at 16/50 at 11:01Z on Groq 429 "tokens per day (TPD): Limit 200000, Used 197584". structured_output_failures so far: 0 over 16 items; rate_limited_attempts 4 (q016); q017 has 6 logged 429 attempts.
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
- Tests (2026-11-17, after the pyproject and tasks.py changes): `py tasks.py lint` "All checks passed!", "115 files already formatted" (before the exclude: "1 file would be reformatted", results\judge_audit.md); `py tasks.py test` "143 passed, 1 deselected in 18.13s". After the audit change: `py tasks.py lint` "All checks passed!", "115 files already formatted"; `py tasks.py test` "144 passed, 1 deselected in 14.29s". Final (2026-11-18, after the labels): `py tasks.py lint` "All checks passed!", "115 files already formatted"; `py tasks.py test` "144 passed, 1 deselected in 7.41s".

Rerun completed (2026-11-17)
- Step 0: `git log --oneline -3` shows 7ee734e "M08: WIP eval harness, judge split, budget model, json_schema (D23)" at HEAD; not re-made.
- `date -u`: 2026-11-17T15:34:46Z.
- `py tasks.py budget --need openai/gpt-oss-120b=110000:34 --need gemini-embedding-001=400:34`: gpt-oss-120b token_bucket 0/1000 requests, 0/200,000 tokens, 180,000 tokens free at 0.9; gemini-embedding-001 0/1000; both "fits".
- `py tasks.py eval --pipeline baseline --run-dir results/runs/baseline-20261116-1050`: "16 items done, 34 to run", q017 to q050 each "done (1 calls ...)", "All items done", exit 0, one invocation, no 429 and no failed attempt (failed_attempts.jsonl still has the 10 lines from 2026-11-16).
- `py tasks.py budget --need gemini-3.5-flash-lite=100000:42` after the eval: gpt-oss-120b bucket balance 13 requests / 72,062 tokens; gemini-3.5-flash-lite 0/500; gemini-embedding-001 34/1000; "fits".
- `py tasks.py judge --run-dir results/runs/baseline-20261116-1050`: "Judge v1: 0 done, 39 to judge", "Judging complete", exit 0, 0 failures, 0 cached.
- Model misses: cache/budget_model_misses.jsonl does not exist (no per-day 429 in this session), so there are no entries to copy.

Old run vs new run (Overall, from each run's summary.md)

| Field | baseline-20261116-0919 (function_calling) | baseline-20261116-1050 (json_schema strict) |
|---|---|---|
| correct (correctness = 2) | 0.905 (38/42) | 0.905 (38/42) |
| correct or partial (correctness >= 1) | 0.929 (39/42) | 0.929 (39/42) |
| mean correctness (0-2) | 1.833 (n=42) | 1.833 (n=42) |
| citation_support (judged items) | 0.927 (38/41) | 0.974 (38/39) |
| context_hit@5 | 0.810 (34/42) | 0.810 (34/42) |
| mean context_evidence_recall@5 | 0.726 (n=42) | 0.726 (n=42) |
| mean must_mention coverage | 0.929 (n=42) | 0.905 (n=42) |
| false_abstention | 0.024 (1/42) | 0.071 (3/42) |
| abstention_correct (unanswerable) | 1.000 (8/8) | 1.000 (8/8) |
| hallucinated (unanswerable) | 0.000 (0/8) | 0.000 (0/8) |
| p50 / p95 latency_ms | 2016 / 4085 ms | 2208 / 3734 ms |
| mean tokens per question | 2207.960 | 2333.560 |
| structured_output_failures | not measured (at least 6 `400 tool_use_failed` calls, 3 pauses) | 0 (n=50) |
| items with >= 1 structured_output failure | not measured | 0.000 (0/50) |
| rate-limited attempts | not measured | 10 (n=50): q016 4, q017 6 |
| generation tokens (in / out, calls) | 91,874 / 18,524, 50 | 95,674 / 21,004, 50 |
| judge tokens (in / out, calls) | 94,959 / 2,629, 41 | 84,398 / 2,450, 39 |

Ceiling for later pipelines: the baseline is correct on 38/42 answerable items, so M10 and M11 can gain at most 4 items on correctness (q008, q024, q025, q029 in this run). M15 should expect the pipelines to differ mainly in abstention (false abstention 3/42 here), hallucination on unanswerable items (0/8 here), RAGAS faithfulness (M09), and cost and latency, not in correctness.

The false-abstention change (1/42 to 3/42) is recorded in D23 as observed; the net 2 items are inside the D19 3-item noise margin, so it is not attributed to the method.

Items whose verdict or abstention changed between the runs: q006 (2,1) to (2,0); q008 (2,1) to false abstention; q024 (0,0) to (1,1); q025 (0,0) to false abstention; q034 (1,0) to (2,1). q029 is a false abstention in both runs. The context_hit@5 values are identical per item (same retrieval), so the differences come from generation (method change and sampling) and from the judge.

summary.md (results/runs/baseline-20261116-1050/summary.md):

### Run summary: baseline-20261116-1050

Pipeline: baseline. Tracing enabled: True.
Judge: gemini-3.5-flash-lite, prompt version 1 (source judge_v1.jsonl), judged 39/39 eligible items.

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
| citation_support (judged items) | 0.974 (38/39) |
| context_hit@5 (on contexts given to the generator) | 0.810 (34/42) |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.726 (n=42) |
| mean must_mention coverage | 0.905 (n=42) |
| false_abstention | 0.071 (3/42) |
| abstention_correct (unanswerable) | 1.000 (8/8) |
| hallucinated (unanswerable) | 0.000 (0/8) |
| mean llm_calls | 1.000 (n=50) |
| p50 latency_ms | 2208 ms |
| p95 latency_ms | 3734 ms |
| mean tokens per question | 2333.560 (n=50) |
| used_web | 0.000 (0/50) |
| structured_output_failures (failed attempts before success) | 0 (n=50) |
| items with >= 1 structured_output failure | 0.000 (0/50) |
| rate-limited attempts (not counted above) | 10 (n=50) |

#### Per category

| Field | single | multi | version | unanswerable |
|---|---|---|---|---|
| items | 28 | 8 | 6 | 8 |
| answerable n | 28 | 8 | 6 | 0 |
| correct (correctness = 2) | 0.893 (25/28) | 0.875 (7/8) | 1.000 (6/6) | - |
| correct or partial (correctness >= 1) | 0.929 (26/28) | 0.875 (7/8) | 1.000 (6/6) | - |
| mean correctness (0-2) | 1.821 (n=28) | 1.750 (n=8) | 2.000 (n=6) | - |
| citation_support (judged items) | 0.962 (25/26) | 1.000 (7/7) | 1.000 (6/6) | - |
| context_hit@5 (on contexts given to the generator) | 0.786 (22/28) | 0.875 (7/8) | 0.833 (5/6) | - |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.786 (n=28) | 0.500 (n=8) | 0.750 (n=6) | - |
| mean must_mention coverage | 0.893 (n=28) | 0.875 (n=8) | 1.000 (n=6) | - |
| false_abstention | 0.071 (2/28) | 0.125 (1/8) | 0.000 (0/6) | - |
| abstention_correct (unanswerable) | - | - | - | 1.000 (8/8) |
| hallucinated (unanswerable) | - | - | - | 0.000 (0/8) |
| mean llm_calls | 1.000 (n=28) | 1.000 (n=8) | 1.000 (n=6) | 1.000 (n=8) |
| p50 latency_ms | 2062 ms | 2772 ms | 2430 ms | 1822 ms |
| p95 latency_ms | 3447 ms | 3610 ms | 3420 ms | 4181 ms |
| mean tokens per question | 2399.107 (n=28) | 2368.500 (n=8) | 2352.833 (n=6) | 2054.750 (n=8) |
| used_web | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.000 (0/8) |
| structured_output_failures (failed attempts before success) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
| items with >= 1 structured_output failure | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.000 (0/8) |
| rate-limited attempts (not counted above) | 10 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |

#### Totals (generation)

- Tokens in: 95674; tokens out: 21004; LLM calls: 50; calls without usage data: 0
- openai/gpt-oss-120b: 95674 in, 21004 out, 50 calls
- Judge: 84398 in, 2450 out, 39 calls, 0 cached verdicts

Correctness 2 with context_hit@5 = 0 (run baseline-20261116-1050)
Method: for each answerable item with judge correctness 2 and context_hit@5 0, I compared the answer's key facts with the five retrieved chunks (doc_path#anchor shown) by reading them; must_mention terms were also matched by substring. Result: 5 items, all strict-anchor misses (the key facts are in a retrieved chunk from a different anchor than the eval evidence); none answered from memory.
- q012 (single; evidence agentic-rag.mdx#generate-a-query-or-respond). Strict-anchor miss. Context [1] graph-api.mdx#working-with-messages-in-graph-state, under the heading "MessagesState": "there exists a prebuilt state called `MessagesState` ... defined with a single `messages` key which is a list of `AnyMessage` objects and uses the add_messages reducer", which is the answer's content.
- q018 (single; evidence streaming.mdx#stream-modes). Strict-anchor miss: same document, other anchor. Contexts [1], [2], [3], [5] streaming.mdx#llm-tokens (headings "Filter by LLM invocation", "Filter by node") show `stream_mode="messages"` with `(message, metadata)` chunks: "The "messages" stream mode streams LLM tokens with metadata".
- q031 (multi; evidence add-memory.mdx#use-in-subgraphs, use-subgraphs.mdx#call-a-subgraph-inside-a-node). Strict-anchor miss. Context [4] use-subgraphs.mdx#define-subgraph-communication (pass a compiled subgraph to add_node when parent and subgraph share state keys; a wrapper function when schemas differ) and context [3] use-subgraphs.mdx#subgraph-persistence ("The parent graph must be compiled with a checkpointer"; the default subgraph mode "inherits the parent's checkpointer"). The answer omits the wrapper-function case for different schemas; the judge still gave 2.
- q038 (version; evidence event-streaming.mdx#resume-after-an-interrupt). Strict-anchor miss. Context [5] interrupts.mdx#resuming-interrupts ("Key points about resuming": same thread ID; "The value passed to `Command(resume=...)` becomes the return value of the interrupt call") and context [2] graph-api.mdx#input-to-invoke-or-stream (heading "resume").
- q039 (single; evidence thinking-in-langgraph.mdx#handle-errors-appropriately). Strict-anchor miss. Context [3] use-graph-api.mdx#combine-control-flow-and-state-updates-with-command and context [4] graph-api.mdx#return-from-nodes (heading "`update` and `goto`": "Return Command from node functions to update state and route to the next node in a single step").

Model misses (bucket model)
- None so far (2026-11-17: cache/budget_model_misses.jsonl absent; no per-day 429 since the bucket model was adopted).

Open questions for the human
- None pending (audit labels received 2026-11-18).

Proposed follow-ups (out of scope)
- Cache query embeddings at runtime (or in the eval only) so resumed or repeated runs do not re-embed; this touches retrieval, so it needs a decision.
- `.env.example` has `RAGDOCS_ENV=` empty (carried over from M07).
- Groq tool_use_failed: try `with_structured_output(AnswerDraft, method="json_schema", strict=True)` for gpt-oss models (Groq lists gpt-oss-120b under strict json_schema at https://console.groq.com/docs/structured-outputs; langchain-groq 1.1.3 `_STRICT_STRUCTURED_OUTPUT_MODELS`). This changes the pipeline, so it needs its own module and a re-run.
- Cohere rerank calls are not recorded in cache/budget.json. Not needed now: use_reranker is False, so nothing calls Cohere. Add recording if reranking is turned on.

Prerequisites for the next module
- Baseline run of record for M09 and later comparisons: results/runs/baseline-20261116-1050 (effective judge judge_v2.jsonl, prompt version 2). results/summary.md written by `py tasks.py compare results/runs/baseline-20261116-1050`.
- M09 can use the faithful column of results/judge_audit.md (no on q016, q033, q024) to sanity-check RAGAS faithfulness.
- M10 and M11 grader calls on openai/gpt-oss-20b use structured_output_method / structured_output_strict (D23).
