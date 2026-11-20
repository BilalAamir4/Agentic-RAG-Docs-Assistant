M11: Self-RAG
Status: Partial (S1 of 3 done; S2 graph and S3 evaluation not started)
Date: 2026-11-21

Goal
M11 adds a "self_rag" mode to the M10 LangGraph pipeline: decide_retrieval before the corrective path, and verify_answer, regenerate and abstain after generate. It is split into three sessions: S1 groundwork (this file so far), S2 graph, S3 evaluation. S1 writes no self_rag state, prompt, node or wiring; build_graph("self_rag") still raises NotImplementedError("M11"). No Groq, Gemini or Tavily call was made in S1.

Module prompt: "M11 (1/3): groundwork for self-RAG", given by the human on 2026-11-21.

Step 0: state check (2026-11-21, before any code)
- `git status`: tracked tree clean; one untracked file, docs/audit/status-audit-2026-11-09.md. This is the audit report the human ruled on in M10 S1 ("leave docs/audit/ untracked, stage only this session's files by path"). It is not an uncommitted change to tracked files, so the session continued; it stays out of the commit.
- `git log --oneline -5`: 06b2383 M10: corrective RAG pipeline and evaluation; 00d3d85 M10 (2/3); f82849a M10 (1/3); 5d205ef M09 screenshot; a33490b M09. Branch main, 3 commits ahead of origin/main (not pushed).
- docs/progress/PROGRESS.md: M10 row "Done (commit 06b2383)", M11 row "In progress (S1 of 3)".

Step 1: verified facts
Installed versions (importlib.metadata in .venv): langchain-groq 1.1.3, groq 0.37.1, tavily-python 0.8.5, langchain-core 1.6.10, pydantic 2.14.1, requests 2.34.2, httpx 0.28.1. Paths below are under .venv/Lib/site-packages unless they start with src/.

a) Where structured_output_failures is computed and stored (before this session)
- Computed once, in the runner: src/ragdocs/eval/runner.py build_record, line 274 at 06b2383: `scores.structured_output_failures = len(failed) - len(rate_limited)`, where failed is every FailedAttempt logged for the item in <run>/failed_attempts.jsonl (load_failed_attempts) and rate_limited is the subset whose message starts with a Settings.rate_limit_error_prefixes entry ("RateLimitError"; runner.py is_rate_limit, config.py line 84). Line 275 stored rate_limited_attempts.
- Stored per item in per_question.jsonl as scores.structured_output_failures and scores.rate_limited_attempts (src/ragdocs/schemas.py ItemScores). The FailedAttempt list (stage, message, utc) is also stored per item in the record's failed_attempts field.
- report.py only aggregated the stored per-item values: _failure_metrics (src/ragdocs/eval/report.py lines 192 to 210 at 06b2383) summed them into summary keys structured_output_failures, items_with_structured_output_failures and rate_limited_attempts; SUMMARY_ROWS lines 344 to 353 rendered them. compare reads the same summary keys.
- So the miscount was in the stored per-item value (runner), not in aggregation.
- Exception kinds that incremented it: every failed attempt that is not a RateLimitError, whatever its cause. FailedAttempt.message is the error TraceEvent message: for the baseline the full str(exc) with the class name first (src/ragdocs/pipelines/base.py safe_error_message: "<ClassName>: <first line>"); for corrective the exception class name only (src/ragdocs/pipelines/agentic/pipeline.py, except block in _stream_events).
- Occurrences in the committed runs:
  - results/runs/baseline-20261116-0919: no failed_attempts.jsonl and no structured_output_failures field (made before the field existed).
  - results/runs/baseline-20261116-1050: 10 failed attempts, all RateLimitError 429 (TPD) on stage generate: q016 x4, q017 x6. structured_output_failures 0 on every item; rate_limited_attempts q016 4, q017 6. Correct.
  - results/runs/corrective-20261120-1852: 2 failed attempts. q043 message "WebSearchError" (a Tavily requests ConnectionError, status None, per the M10 LangSmith trace) counted as structured_output_failures 1. q049 message "BadRequestError" (Groq 400 json_validate_failed on rewrite_query, per the M10 LangSmith trace) counted as 1.

b) json_validate_failed and parse/validation errors
- Groq raises groq.BadRequestError (groq/_exceptions.py line 79, subclass of APIStatusError, line 57) for any HTTP 400 (groq/_client.py _make_status_error line 223). status_code is 400 (line 80).
- Its body is the decoded JSON response, stored unchanged: _make_status_error_from_response (groq/_base_client.py lines 400 to 420) does json.loads(response.text) and APIError.__init__ (groq/_exceptions.py lines 40 to 44) stores it as exc.body. For q049 the body was {"error": {"message": "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.", "type": "invalid_request_error", "code": "json_validate_failed", "failed_generation": ""}} (M10 S3 additional facts, item 3, from the LangSmith trace). The identifying field is exc.body["error"]["code"] == "json_validate_failed". Other 400s carry another code, so json_validate_failed can be told apart from other 400 errors when the exception object is available.
- langchain-groq passes the groq exception through unwrapped: ChatGroq has no except clause around the client call (langchain_groq/chat_models.py; the only except clauses are line 538, ImportError, and line 1514, inside streaming tool-call parsing).
- with_structured_output(schema, method="json_schema", strict=True) (D23) builds `llm | PydanticOutputParser(pydantic_object=schema)` (langchain_groq/chat_models.py lines 1214 to 1253, line 1278). PydanticOutputParser.parse_result (langchain_core/output_parsers/pydantic.py lines 57 to 82) raises langchain_core.exceptions.OutputParserException for invalid JSON (from JsonOutputParser, json.py line 91) and also for JSON that parses but fails validation: pydantic.ValidationError is caught and re-raised as OutputParserException (pydantic.py lines 36 to 45). OutputParserException subclasses ValueError (langchain_core/exceptions.py line 15). A bare pydantic.ValidationError therefore does not escape the parser; it can still come from project code that validates afterwards, so the existing corrective grader catches both (src/ragdocs/pipelines/agentic/nodes.py line 42 GRADING_PARSE_ERRORS = (OutputParserException, ValidationError)).
- How the runner handled q049 (M10 tracking file S3 Step 1 and additional facts item 3; corrective run folder): the 400 ended the graph with one error event whose message is "BadRequestError" (class name only). The runner appended {"id": "q049", "stage": "grade_documents", "message": "BadRequestError", "utc": "2026-11-20T20:07:32+00:00"} to failed_attempts.jsonl (stage reads grade_documents because rewrite_query emits node_start only in its return value), retried the whole item (eval_item_attempts), and the second attempt completed (4 calls, web fallback, abstained). per_question.jsonl stores structured_output_failures 1, rate_limited_attempts 0 and the same failed_attempts entry. Nothing in the run folder records the status code, the body or the code json_validate_failed; only the class name.

c) Tavily connection errors and timeouts (tavily-python 0.8.5)
- TavilyClient.search posts with self.session.post (tavily/tavily.py line 238) inside `except requests.exceptions.Timeout: raise TimeoutError(timeout)` (lines 239 to 240). Other requests exceptions are not caught.
- A connection error raises requests.exceptions.ConnectionError (requests/exceptions.py line 70, subclass of RequestException, line 20, which subclasses IOError = OSError). It has no response, so status is None.
- A timeout (requests.exceptions.Timeout, line 82, including ReadTimeout line 98 and ConnectTimeout line 91, which subclasses both ConnectionError and Timeout) is re-raised as tavily.errors.TimeoutError (not an OSError).
- Non-2xx responses (_handle_error_response, tavily.py lines 116 to 143): 429 UsageLimitExceededError, 403/432/433 ForbiddenError, 401 InvalidAPIKeyError, 400 BadRequestError, anything else requests.HTTPError via raise_for_status.
- TavilySearch before this session (src/ragdocs/providers/websearch.py _call, lines 84 to 112 at 06b2383): up to Settings.web_search_max_attempts (3) attempts; backoff starts at Settings.web_search_backoff_s (1.0 s) and doubles (1 s, 2 s). Retried: UsageLimitExceededError (429) and OSError with status 5xx. Raised at once: InvalidAPIKeyError as WebSearchAuthError; ForbiddenError, BadRequestError and tavily TimeoutError as WebSearchError; and any OSError whose status is None or not 429/5xx, which includes requests.ConnectionError (q043).

d) Groq 429 retries
- src/ragdocs/providers/llm.py lines 74 and 84 build ChatGroq with max_retries=3 for the generator and grader; langchain-groq passes it to the groq client (chat_models.py line 520). groq's own default is 2 (groq/_constants.py line 10).
- groq/_base_client.py request loop (lines 960 to 1047): up to max_retries + 1 = 4 attempts. HTTP errors are retried when _should_retry (lines 748 to 779) is true: header x-should-retry "true" (or never when "false"), else 408, 409, 429 and >= 500. 400 and 401 are not retried. httpx timeouts and other transport exceptions are also retried and finally raise APITimeoutError / APIConnectionError (lines 984 to 1011).
- Retry-After: _calculate_retry_timeout (lines 722 to 745) honours retry-after-ms, then retry-after (seconds or HTTP date) only when 0 < value <= 60 s. Otherwise exponential backoff 0.5 s x 2^n capped at 8 s (constants lines 13 to 14) with up to 25% jitter downwards.
- After the retries, RateLimitError reaches the eval runner, which logs the attempt, waits for the parsed retry-after (default Settings.rate_limit_default_wait_s 60 s) plus 1 s and retries the item without spending an item attempt (runner.py _run_one, handle_rate_limit), pausing with exit 3 past rate_limit_max_wait_s or rate_limit_max_waits_per_item.

e) generate_answer before this session (src/ragdocs/generation/answer.py lines 158 to 170 at 06b2383)
- Signature: `generate_answer(question: str, chunks: Sequence[RetrievedChunk | Chunk], llm: StructuredLLM) -> tuple[Answer, dict[str, Any]]`.
- Messages, in order: SystemMessage(content=ANSWER_SYSTEM_PROMPT); HumanMessage(content=ANSWER_USER_TEMPLATE.format(question=question, context=format_context(chunks))). Then llm.invoke(messages) and validate_answer(draft, chunks).

Other facts found while verifying
- PipelineResult (src/ragdocs/schemas.py) had no diagnostics field. Corrective diagnostics (grading_failures, missing_grades, invalid_grades, rewrite_unchanged, web_duplicates_dropped, dropped_citations, uncited) live only in the graph state and the LangSmith parent run outputs (pipeline.py _parent_outputs). No stored per_question.jsonl result in any run has a "diagnostics" key.
- tests/test_baseline_snapshot.py compares the full BaselinePipeline stream dump, including the answer event's PipelineResult dump, with tests/fixtures/baseline_stream_snapshot.json. A new PipelineResult field that is always serialised would change that dump.
- pydantic 2.14.1 supports Field(exclude_if=...): a probe model with `d: dict = Field(default_factory=dict, exclude_if=lambda v: not v)` dumped {'a': 1} when d was empty and included d when it held a value; validating a dict without the key gave d == {}.
- Settings.max_regenerations = 1 already existed (src/ragdocs/config.py, added in M00 commit 7aceeae; asserted in tests/test_config.py line 49) and nothing used it.

Pre-registered expectations (written before the self_rag eval)
Written 2026-11-21 from the committed corrective run results/runs/corrective-20261120-1852 (and the baseline run for item 3). No self_rag code or result exists yet. Correctness is the judge_v2 verdict; an abstained answerable item counts as correctness 0 (report rule).

1. Grader-accepted retrieval misses: answerable items with first_retrieval_hit@5 = 0 whose first grading routed straight to generate (decision event branch "generate"; node path retrieve, grade_documents, generate). 7 items, as M10 found:

  | id | category | corrective correctness | abstained |
  |---|---|---|---|
  | q008 | single | 0 (false abstention, not judged) | yes |
  | q012 | single | 2 | no |
  | q018 | single | 2 | no |
  | q024 | single | 0 | no |
  | q031 | multi | 2 | no |
  | q038 | version | 2 | no |
  | q039 | single | 2 | no |

  - Expectation: none of these can become correct under self_rag because of better retrieval, since there is no edge from verify back to retrieval. Possible self_rag outcomes per item: the same answer, a regenerated answer from the same contexts, or an abstention.
  - Note: 5 of the 7 (q012, q018, q031, q038, q039) are already correct in corrective without gold evidence in the first retrieval, so for them the expectation is "stays correct, or regresses through regeneration or abstention". The two that are not correct (q008 abstained, q024 correctness 0) are expected not to become correct (2). For q008, decide_retrieval could only change the path before retrieval, and the same retrieval would follow.

2. The 8 items that reached rewrite_query (each: first grading 0 of 5, rewrite, second grading 0 of 5, web search, generate; 4 LLM calls; used_web True):

  | id | category | corrective outcome |
  |---|---|---|
  | q025 | single | false abstention (web search returned 3 results, none the gold page) |
  | q043 | unanswerable | abstained (abstention_correct) |
  | q044 | unanswerable | abstained (abstention_correct) |
  | q045 | unanswerable | abstained (abstention_correct) |
  | q046 | unanswerable | abstained (abstention_correct) |
  | q048 | unanswerable | abstained (abstention_correct) |
  | q049 | unanswerable | abstained (abstention_correct); first attempt failed with the Groq 400 json_validate_failed |
  | q050 | unanswerable | abstained (abstention_correct) |

  - The second retrieval produced a relevant chunk on 0 of 8.

3. q024 and q034 (the two items that regressed from baseline to corrective):

  | id | category | baseline (correctness, citation_support) | corrective |
  |---|---|---|---|
  | q024 | single | (1, 1) | (0, 0) |
  | q034 | multi | (2, 1) | (1, 0) |

  - Judge v2 rationales (judge_v2.jsonl, verbatim):
    - q024 baseline: "The assistant correctly explains that parallel branches run in the same superstep and writes cause conflicts, but misses mentioning reducers (like operator.add) as the primary solution, which is key in the reference answer."
    - q024 corrective: "The assistant's answer contradicts the reference answer. It attributes parallel branching write failures to inconsistent ordering rather than missing reducers, missing the core mechanism of concurrent updates and `operator.add`."
    - q034 baseline: "The assistant correctly explained how to use graph.get_state and graph.update_state with proper thread configs, matching the reference answer and supported by the cited excerpts."
    - q034 corrective: "The assistant correctly describes reading state with get_state. However, it invents an incorrect API for updating state by suggesting an '@update_state' decorator on a node function, rather than using graph.update_state(config, values). Additionally, the claim about the edit node lacks citation support since excerpt 4 discusses update_state differently."
  - Expectation: these are the items where verify_answer and regenerate could change the outcome (an unsupported claim the verifier can flag against the given contexts). q024's first retrieval had no gold evidence (item 1), so a regenerated q024 answer still has only the same graded excerpt to work from. q034's first retrieval held gold evidence (first_retrieval_hit@5 1).

4. Cost forecast (Groq; from per_question.jsonl usage of the corrective run and cache/budget.json events for its run window)
- Corrective, grader model openai/gpt-oss-20b (grade and rewrite calls): 138,872 tokens over 66 calls for 50 items. Per item: mean 2,777 tokens and 1.32 calls; max 5,672 tokens (q043) and 3 calls (the 8 rewrite items).
- Mean tokens per grading call: 2,301 (61 grading calls in cache/budget.json between 2026-11-20 18:50Z and 20:35Z, including q043's failed first attempt; the 9 rewrite calls of 509 to 905 tokens excluded). For comparison, the 42 single-call items averaged 2,392 grader tokens.
- Self_rag estimate per item, grader model: corrective + 1 decide + 1 or 2 verify, each at 2,301 tokens. Mean 2,777 + 2 x 2,301 = 7,379 to 2,777 + 3 x 2,301 = 9,680 tokens; 3.32 to 4.32 calls.
  - The stand-in is an assumption. A decide call sees only the question and is likely smaller. A verify call sees the answer plus the contexts and could be larger than a grading call.
- Per 50-item run, grader model: 368,950 to 484,000 tokens; 166 to 216 requests (the cap is 1,000 RPD x 0.9 = 900).
- Days of quota at the Settings limits (groq_tpd_limit 200,000 per model, throttle_safety 0.9, token bucket refilling 200,000 per 24 h = 2.315 tokens/s): the first 180,000 tokens are available at once, then about 200,000 per day. That gives 1 + (368,950 - 180,000) / 200,000 = 1.9 days to 1 + (484,000 - 180,000) / 200,000 = 2.5 days. Plan for 2 to 3 calendar days on gpt-oss-20b, starting from a drained bucket.
- Generator openai/gpt-oss-120b: corrective used 89,993 tokens over 50 calls (max item 4,409). Regenerate adds at most 1 generator call per item. If every item regenerated, about 180,000 tokens, which is the 0.9 cap for one day. Far fewer regenerations are expected.
- Worst-case item, grader model: 5,672 + 3 x 2,301 = 12,575 tokens over 6 calls (decide 1, grade 2, rewrite 1, verify 2). That exceeds the 8,000 tokens-per-minute limit (7,200 at 0.9) on its own. S3 therefore relies on the 429 handling verified in Step 1d: groq retries up to 3 times, honouring Retry-After up to 60 s, then the runner waits out the 429 without spending an item attempt. It also relies on the throttle, which waits per model and proceeds once the per-minute window is empty (M10 S3 check a). The largest measured single call is 5,151 tokens (q008 grading), below the 7,200 per-call STOP rule.

What was built
- src/ragdocs/providers/errors.py (new, runtime-safe: imports groq, pydantic and langchain-core only):
  - ErrorKind and ERROR_KINDS.
  - is_structured_output_error(exc): True exactly for a groq 400 with body error.code json_validate_failed, OutputParserException and pydantic ValidationError.
  - error_kind(exc) for live exceptions; it reads WebSearchError.kind.
  - classify_message(message, rate_limit_prefixes) for stored messages.
  - groq_error_code(exc).
- src/ragdocs/eval/failures.py (new, offline): KIND_FIELDS, attempt_kind, count_kinds, item_kinds (applies overrides), load_overrides, overrides_for_run, overrides_path.
- src/ragdocs/schemas.py:
  - PipelineResult.diagnostics: dict, default {}, left out of dumps when empty.
  - FailedAttempt.kind (optional).
  - ItemScores.transient_call_errors, permanent_call_errors, unclassified_call_errors (optional).
  - ErrorReclassification model (run, item, kind, evidence with at least 1 entry, optional utc).
- src/ragdocs/eval/runner.py:
  - Failed attempts take their kind from the error event's data["error_kind"], else from classify_message.
  - build_record counts the five kinds into their own fields. structured_output_failures now counts only structured_output.
  - The rate-limit wait logic is unchanged.
- src/ragdocs/eval/report.py:
  - Failure counts are recomputed from the stored attempts (record_kinds), with overrides applied.
  - New summary keys transient_call_errors, permanent_call_errors and unclassified_call_errors.
  - structured_call_fallbacks: items with at least one diagnostics["fallbacks"] entry, as rate (count/n), plus occurrences per type.
  - summary["error_reclassifications"] when an override was applied, rendered as a note under the Overall table (reclassification_notes).
  - Four rows appended after the existing failure rows; FALLBACK_TYPES.
- src/ragdocs/eval/compare.py: prints the same override notes under its Overall table.
- src/ragdocs/pipelines/agentic/pipeline.py: the error event gets data {"error_kind": error_kind(exc)}. The message is unchanged; nodes, prompts and wiring are untouched.
- src/ragdocs/providers/websearch.py:
  - Connection errors (requests ConnectionError) and timeouts (tavily TimeoutError, requests Timeout) are retried with the existing attempts and backoff.
  - WebSearchError carries kind: "transient" for connection, timeout and 429/5xx after the retries; "permanent" for 403/432/433, 400, 401 and other HTTP statuses; "unclassified" otherwise.
- src/ragdocs/generation/answer.py: generate_answer(..., extra_messages: list[BaseMessage] | None = None), appended after the two existing messages.
- src/ragdocs/config.py: a comment on max_regenerations (value unchanged, 1); error_reclassifications_file = "error_reclassifications.json" (read from results_dir).
- .env.example: MAX_REGENERATIONS=1 comment, in the same block style as MAX_QUERY_REWRITES.
- results/error_reclassifications.json (new; human decision): overrides for corrective-20261120-1852 q049 (structured_output) and q043 (transient), each pinned by utc and listing its evidence.
- docs/DECISIONS.md: D23 update (failed attempts counted by kind; override file), D26 (self-RAG structured-call failure policy), D27 (self-RAG LLM call bound).
- docs/progress/PROGRESS.md: M10 and M11 rows. docs/progress/M11-self-rag.md (this file).
- Tests (new files):
  - tests/test_provider_errors.py: every exception kind built directly, plus message classification.
  - tests/test_failure_kinds.py: hand-made per-item data covering each kind; unknown message counts as unclassified; override applied and noted in summary.md and compare; missing override file means no overrides; other run or utc is ignored; evidence required; fallback rate and per-type counts; no diagnostics key means no fallbacks; diagnostics dump rules.
  - tests/test_error_kind_events.py: error_kind on the agentic error event; the runner counts by event kind, and by message when the event has none.
  - tests/test_generate_answer_messages.py with tests/fixtures/generate_answer_messages.json.
- Tests (additions): tests/test_websearch.py (+10: connection error then success after 2 attempts; connection errors on every attempt raise after 3; timeouts; 401 after 1 attempt; 403/432/433 and 400 permanent; 429/5xx after retries transient; other status permanent); tests/test_import_boundaries.py (+2: errors.py imports no other ragdocs module; the agentic pipeline stays runtime-safe).
- tests/eval_fakes.py: FakePipeline's default fail_message (see Deviations).

How to run
- `py tasks.py compare results/runs/baseline-20261116-1050 results/runs/corrective-20261120-1852` shows the new rows and the override notes (not run in S1; see Known issues).
- In code: `from ragdocs.providers.errors import is_structured_output_error, error_kind`; `generate_answer(question, chunks, llm, extra_messages=[...])`.
- `.venv\Scripts\python tests\test_generate_answer_messages.py --write` rewrites the message fixture. Do this only on an intended answer-prompt change, which needs a DECISIONS.md entry.

Verification
- Before any change: `py tasks.py test` "243 passed, 1 deselected in 11.45s"; `py tasks.py lint` "143 files already formatted".
- Message fixture: written from the unchanged generate_answer, then test_default_messages_match_fixture_byte_for_byte passed on the unchanged code. After the change, all 3 message tests and the baseline snapshot test passed (5 passed).
- After the classifier change and before the fake-message change, the full suite had exactly one failure: tests/test_eval_runner.py::test_run_eval_resume_skips_done_ids (`assert 0 == 2` at line 126). The human had listed it as the only user of FakePipeline's default fail_message (grep: tests/eval_fakes.py:140 default; tests/test_eval_runner.py lines 116 default; 244, 280, 300 set their own message). After the one-line fake change the suite passed, so no other test changed outcome.
- Final (2026-11-21, before commit):
  - `py tasks.py lint`: "All checks passed!", "149 files already formatted".
  - `py tasks.py test`: "319 passed, 1 deselected in 12.02s" (243 + 76 new).
  - `py tasks.py bundle-check`: "Total bundle size: 229.96 MB (limit: 400.00 MB)", exit 0.
  - The baseline snapshot test, the new message-fixture tests and every M10 test pass with their assertions unchanged.
- `git diff --stat 06b2383 -- tests/ results/`: tests/eval_fakes.py (5 lines, the approved fail_message), tests/test_websearch.py (imports plus appended tests), tests/test_import_boundaries.py (appended test). New untracked: 4 test files, 1 fixture, and results/error_reclassifications.json. No file under results/runs/ changed. No existing assertion changed.
- structured_output_failures, old (stored summary.json, written by the M10 runner and report) against new (summarize() recomputed in memory; no run-folder file written):

  | run | row | old | new |
  |---|---|---|---|
  | baseline-20261116-0919 | all failure rows | - | - (made before the field existed) |
  | baseline-20261116-0919 | structured-call fallbacks | (row did not exist) | 0.000 (0/50) |
  | baseline-20261116-1050 | structured_output_failures | 0 (n=50) | 0 (n=50) |
  | baseline-20261116-1050 | items with >= 1 structured_output failure | 0.000 (0/50) | 0.000 (0/50) |
  | baseline-20261116-1050 | rate-limited attempts | 10 (n=50) | 10 (n=50) |
  | baseline-20261116-1050 | transient / permanent / unclassified call errors | (rows did not exist) | 0 / 0 / 0 (n=50) |
  | baseline-20261116-1050 | structured-call fallbacks | (row did not exist) | 0.000 (0/50) |
  | corrective-20261120-1852 | structured_output_failures | 2 (n=50) | 1 (n=50) |
  | corrective-20261120-1852 | items with >= 1 structured_output failure | 0.040 (2/50) | 0.020 (1/50) |
  | corrective-20261120-1852 | rate-limited attempts | 0 (n=50) | 0 (n=50) |
  | corrective-20261120-1852 | transient call errors | (row did not exist) | 1 (n=50) (q043) |
  | corrective-20261120-1852 | permanent / unclassified call errors | (rows did not exist) | 0 / 0 (n=50) |
  | corrective-20261120-1852 | structured-call fallbacks | (row did not exist) | 0.000 (0/50) |
  | corrective-20261120-1852, unanswerable | structured_output_failures | 2 (n=8) | 1 (n=8) |
  | corrective-20261120-1852, unanswerable | items with >= 1 structured_output failure | 0.250 (2/8) | 0.125 (1/8) |

  - No other overall summary key changed value in any of the three runs (checked key by key).
  - Without the override file, corrective would show structured_output_failures 0 and unclassified_call_errors 2, because its stored messages are the bare class names "WebSearchError" and "BadRequestError".
  - Reason for the overrides:
    - q049: the run folder stores only "BadRequestError". The human ruled that a bare BadRequestError must not be treated as structured. The M10 tracking file ("S3 additional facts", item 3) records the LangSmith trace's Groq 400 with code json_validate_failed, which was checked before adding the entry.
    - q043: a bare "WebSearchError" can be transient or permanent. The M10 tracking file ("S3 Step 1", failed attempts) records the tavily_search run's "ConnectionError (status None)".
    - The LangSmith run ids in the evidence are per_question.jsonl's langsmith_run_id, which is the eval_item run of the attempt that succeeded. The failed attempts' own trace ids are not stored.
  - The override note as rendered: "- Note: corrective-20261120-1852 q049: failed-attempt kind set to structured_output by results/error_reclassifications.json (the stored message cannot show it). Evidence: ..." (same form for q043).

Decisions made
- Failed attempts are counted by kind, and stored kinds come from the error event (human decision, 2026-11-21). Recorded as a D23 update.
- Stored messages that do not identify a kind on their own are unclassified; an evidence-backed override file corrects them (human decision). Two entries, q049 and q043 (human approved the q043 entry).
- WebSearchError kinds: transient only for connection errors, timeouts and 429/5xx after the retries; permanent for 403/432/433 and 400 (human decision). 401 (WebSearchAuthError) and other HTTP statuses are also permanent (my choice: they do not succeed on retry). An OSError with no status that is not a connection error is unclassified.
- PipelineResult.diagnostics, left out of dumps when empty; only self_rag fills it; S2 also puts data["fallback"] on the failed node's decision event (human decision). Recorded in D26.
- D26 failure policy and D27 call bound added. The reason for the decide_retrieval rule (retrieving costs little; skipping on a broken decision would answer without documentation) is mine; the prompt gave reasons for the verify and regenerate rules only.
- Per-type fallback counts are occurrences, not items, because verify_answer can fail on both verifications of one item.

Deviations from the prompt
- The Tavily retry fix changes corrective's behaviour only when a connection error or timeout occurs. Such a search is now retried up to 3 attempts in total (1 s, 2 s backoff) instead of failing at once. No stored corrective result is affected, because stored results are not regenerated. The message for an exhausted timeout changes from "Tavily search failed: TimeoutError" to "Tavily search failed after 3 attempt(s): TimeoutError (status None)".
- results/ is no longer unchanged against 06b2383. results/error_reclassifications.json was added at the human's instruction, which came after the prompt's acceptance check. Nothing under results/runs/ changed. results/summary.md was not regenerated.
- tests/eval_fakes.py line 140, FakePipeline's default fail_message, changed from "BadRequestError: 400" to a Groq json_validate_failed message (human approved). The fake was always meant to stand for a structured-output failure, and the new classifier needs the real error code to recognise one. The new test that a bare "BadRequestError: 400" counts as unclassified is kept (tests/test_error_kind_events.py and tests/test_failure_kinds.py).
- tests/test_websearch.py: `py tasks.py format` (ruff) merged the new `from tavily import BadRequestError` into the existing tavily import line. Only imports changed; no assertion changed.
- ItemScores.permanent_call_errors and its summary row were added besides transient_call_errors. The permanent kind needed a counter, and the prompt says to add one when none covers an error.
- The override entries carry an optional utc (beyond run, item, kind, evidence), so each one applies only to the failed attempt it was written for.
- The fallback row renders "0.000 (0/50)", the same rate format as every other rate row, not "0 (0/50)".
- max_regenerations already existed in Settings (M00). Only the comment and the .env.example line were added.
- AgenticPipeline (pipeline.py) changed: data["error_kind"] on the error event (human approved). This is not a corrective node, prompt or wiring change, and the error message text is unchanged.

Known issues and limitations
- Committed run folders keep their old summary.json and summary.md (2 structured-output failures for corrective). results/summary.md (M10 compare output) also still shows the old rows. The next `py tasks.py compare` (S3) will show the new values with the override notes.
- Stored agentic messages are bare class names, so any future stored-only ambiguity needs another override entry. New runs avoid this through FailedAttempt.kind.
- failed_attempts "stage" still reads the last node_start before the error (M10 known issue, not changed).
- The cost forecast uses the mean grading call as a stand-in for decide and verify calls.

Open questions for the human
- Open: how a caught self_rag fallback enters structured_output_failures. D26 says every caught failure counts there, but the count is built from failed attempts (items that ended in an error event), and a caught fallback does not end the item. One option: the report adds len(diagnostics["fallbacks"]) to the item's structured_output_failures, which leaves baseline and corrective unchanged because they have no fallbacks. The row label "failed attempts before success" would then need a wording change. Not built in S1; for the human or S2 to decide and record in DECISIONS.md.
- Resolved on 2026-11-21:
  - Recount method: forward error_kind, message classification, override file (q049).
  - Fallback storage: PipelineResult.diagnostics, left out of dumps when empty.
  - Existing test conflict: change the fake's default message.
  - q043: second override entry; WebSearchError transient or permanent kinds.

Proposed follow-ups (out of scope)
- Record the failed attempt's own LangSmith run id in FailedAttempt, so evidence for an override can point at the failing trace.
- Fix the failed_attempts stage for nodes that emit node_start only in their return value (M10 follow-up, still open).
- Groq 400 json_validate_failed on corrective's grader or rewriter still ends the graph with an error event (M10 follow-up for M12). D26 covers only self_rag's new calls.

Prerequisites for the next session (S2)
- See "Handoff to S2".

Handoff to S2
- Names to use:
  - Errors helper: `from ragdocs.providers.errors import is_structured_output_error` (also error_kind, classify_message, ErrorKind). Catch a failed structured call with `except Exception as exc: if not is_structured_output_error(exc): raise`, or an equivalent narrow catch, so rate-limit, auth and connection errors propagate unchanged (D26).
  - Setting: `Settings.max_regenerations` (int, default 1; env MAX_REGENERATIONS). Use it next to `Settings.max_query_rewrites` (1).
  - Fallback values in `diagnostics["fallbacks"]` (a list of str, appended in order): "decide_failed", "verify_failed", "regenerate_failed" (report.FALLBACK_TYPES). The failed node's decision event also gets `data["fallback"]` with the same value.
  - `PipelineResult.diagnostics`: only self_rag mode copies graph-state diagnostics into it (in AgenticPipeline, when mode == "self_rag"). Corrective must keep an empty dict, so its dumps stay byte-identical to M10 and no M10 test changes. The report counts a missing key as no fallbacks.
  - Count each caught failure in the item's structured_output_failures. The runner counts failed attempts only, so S2 must decide how a caught in-graph failure reaches that count (for example the report adding the length of diagnostics["fallbacks"]), and record the choice in DECISIONS.md.
  - Generation with extra messages: `generate_answer(question, chunks, llm, extra_messages: list[BaseMessage] | None = None)`. The messages are appended after the system prompt and the user turn; with None the sent messages equal tests/fixtures/generate_answer_messages.json.
  - Agentic error events carry `data["error_kind"]` (unchanged message).
- D numbers: D26 (self-RAG structured-call failure policy), D27 (8-call bound). The D23 update covers failed-attempt kinds and the override file.
- Structured-output method (D23): `with_structured_output(schema, method="json_schema", strict=True)` through Settings.structured_output_method ("json_schema") and Settings.structured_output_strict (True); bind with ragdocs.pipelines.agentic.graph.bind_structured as the corrective grader does.
- Outcomes (D25): decide_retrieval failure gives "info"; verify_answer failure gives "info" and routes to END; regenerate failure abstains with abstain_reason "regenerate_failed" and outcome "stop".
- Open questions: one, how caught fallbacks enter structured_output_failures (see "Open questions for the human").
- Pre-registered expectations for S3 are above. Do not edit them after the self_rag eval runs.
