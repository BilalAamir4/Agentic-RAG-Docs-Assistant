M11: Self-RAG
Status: Done
Date: 2026-11-22
Tag v2-agentic: 56a5043633f81822900d2e9cf6856f6db2059f80

Goal
M11 adds a "self_rag" mode to the M10 LangGraph pipeline: decide_retrieval before the corrective path, and verify_answer, regenerate and abstain after generate. It is split into three sessions: S1 groundwork, S2 graph (section "Session 2" below), S3 evaluation. S1 wrote no self_rag state, prompt, node or wiring and made no Groq, Gemini or Tavily call. S2 built the graph and ran the decide probe and four smoke asks; it ran no eval, ragas or experiment.

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

5. q028 is routed out of scope (added in S2, 2026-11-21, from the decide probe, before the self_rag eval; human decision to keep DECIDE_SYSTEM_PROMPT unchanged)
  - q028 (single, answerable; "In Pregel, which channel is used by default, and what happens to earlier values?"; gold pregel.mdx#topic) is routed to out_of_scope by decide_retrieval, reason "Question about Pregel, not LangGraph." (cache/decide_probe.jsonl).
  - Expected in S3: a false abstention (the out-of-scope text, abstained, no contexts).
  - It also counts as a first_retrieval_hit@5 miss, because it has no retrieval event (M10 rule: an answerable item with no retrieval event is a miss). S3 must name q028 beside the first-retrieval hit@5 row, so the miss is not read as a retrieval regression.
  - The probe is one sample per question; S3's call can differ from it.

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
- Resolved in S2 (2026-11-21, human decision, D26 amendment): how a caught self_rag fallback enters structured_output_failures. It does not: a caught fallback is recorded in diagnostics["fallbacks"] and counted only in the structured-call fallbacks row. structured_output_failures keeps its meaning (failed attempts that ended an item in an error event), so the three pipelines stay comparable on that row. The total of failed structured calls for self_rag is the sum of the two rows. The report's counting is unchanged.
- Resolved in S2 (2026-11-21): q028 routed out of scope by the decide probe. Human: keep the prompt; record the expectation (Pre-registered expectations, item 5) and a follow-up.
- Resolved in S2 (2026-11-21): two placeholder assertions in tests/test_corrective_pipeline.py (see Session 2, Deviations).
- Resolved on 2026-11-21 (S1):
  - Recount method: forward error_kind, message classification, override file (q049).
  - Fallback storage: PipelineResult.diagnostics, left out of dumps when empty.
  - Existing test conflict: change the fake's default message.
  - q043: second override entry; WebSearchError transient or permanent kinds.

Proposed follow-ups (out of scope)
- Record the failed attempt's own LangSmith run id in FailedAttempt, so evidence for an override can point at the failing trace.
- Fix the failed_attempts stage for nodes that emit node_start only in their return value (M10 follow-up, still open).
- Groq 400 json_validate_failed on corrective's grader or rewriter still ends the graph with an error event (M10 follow-up for M12). D26 covers only self_rag's new calls.
- (S2) decide_retrieval false negative on a question that names a LangGraph component without the word "LangGraph" (q028: Pregel). Any prompt change must be validated on questions outside the eval set, never by re-running the probe on it. Not done in M11.
- (S2) The answer text printed by ask.py for q009 shows a code block with its indentation lost. This is the generator's output through the shared answer path (not a self_rag change); worth a check in M12/M13 when answers are rendered.

Prerequisites for the next session
- S2: see "Handoff to S2" (done). S3: see "Handoff to S3" at the end of this file.

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
- Open questions: one, how caught fallbacks enter structured_output_failures (see "Open questions for the human"). Resolved in S2 by the D26 amendment.
- Pre-registered expectations for S3 are above. Do not edit them after the self_rag eval runs.

Session 2: self-RAG graph and pipeline (2026-11-21)
Module prompt: "M11 (2/3): self-RAG graph and pipeline", given by the human on 2026-11-21.

S2 Step 0: D26 amendment
- Appended to D26 in docs/DECISIONS.md, word for word as given ("Amended 21 Nov 2026: ..."). The report's counting is unchanged. The S1 open question is marked resolved above.

S2 Step 1: verified facts (langgraph 1.2.14, langchain-core 1.6.10, from importlib.metadata in .venv; paths under .venv/Lib/site-packages)
- Each fact was checked in the source and with a throwaway script in the session scratchpad (not committed).
- a) Conditional edges with END.
  - Source: langgraph/graph/state.py add_conditional_edges (line 982) builds BranchSpec.from_path (langgraph/graph/_branch.py line 89). A dict path_map is copied and a list becomes an identity map. With no path_map, the ends come only from a Literal return hint on the routing function, else None. _finish (line 192) maps the returned value through ends. END is the string "__end__" (langgraph/constants.py line 28). validate (state.py line 1129) accepts END as a branch target.
  - Probe, routing function returning END or "b":
    - Without a path map, the graph routes correctly, but the Mermaid export drew only `a --> __end__;` and no edge to b.
    - With the explicit path map {"b": "b", END: END}, it drew `a -.-> __end__;` and `a -.-> b;` (dotted = conditional), plus `b --> __end__;`.
  - So every self_rag conditional edge uses an explicit identity path map, END included.
- b) Exceptions handled inside a node.
  - Source: langgraph/pregel/_retry.py run_with_retry (line 575). It returns task.proc.invoke(...) and only reaches the retry policy through its except branches, so a node that catches its own exception returns normally. The retry policy is task.retry_policy or the compile default. The project's add_node and compile calls pass none.
  - Probe: a node that raised and caught an exception, then returned an update, led to the next node running. stream_mode="updates" gave both updates, and builder.nodes["n1"].retry_policy was None.
- c) State key without a reducer.
  - Source: such a key is a LastValue channel (langgraph/channels/last_value.py line 20). update (line 56) stores values[-1], so the whole value is replaced.
  - Probe: initial diag {"k": 0}; node 1 returned {"fallbacks": [...]}, node 2 returned {"other": 1}; the final diag was {"other": 1}. The channel type was LastValue.
  - So every self_rag node that writes diagnostics returns a merged copy (self_rag_nodes.with_fallback; {**state["diagnostics"], ...}).

S2 What was built
- src/ragdocs/pipelines/agentic/state.py:
  - RetrievalDecision(needs_docs, reason) and AnswerVerification(grounded, unsupported_claims, answers_question). Length limits are in the Field descriptions only, with no validators.
  - AgentState gains needs_docs, regenerations and verification as NotRequired keys. initial_state(question, mode="corrective") sets them only for "self_rag", so the corrective graph input is unchanged.
  - AgenticDeps gains decider_llm and verifier_llm, both defaulting to None.
- src/ragdocs/pipelines/agentic/prompts.py: DECIDE_SYSTEM_PROMPT, DECIDE_USER_TEMPLATE, VERIFY_SYSTEM_PROMPT, VERIFY_USER_TEMPLATE, REGENERATE_FEEDBACK_TEMPLATE and OUT_OF_SCOPE_TEXT, with the exact prompt text. The corrective prompts are unchanged.
- src/ragdocs/pipelines/agentic/self_rag_nodes.py (new): the nodes decide_retrieval, out_of_scope, verify_answer, regenerate and abstain, plus the helpers with_fallback, verify_route, feedback_claims and feedback_message. The D26 catch uses is_structured_output_error and re-raises everything else. Fallback events carry data["fallback"] and data["error_kind"].
- src/ragdocs/pipelines/agentic/graph.py:
  - build_graph builds "self_rag" with the wiring below and "corrective" as in M10. The corrective nodes are added in the same order through the same partials, so corrective.mmd is byte-identical.
  - route_next_step routes self_rag; the path maps are DECIDE_BRANCHES, VERIFY_BRANCHES (END, "regenerate", "abstain") and REGENERATE_BRANCHES.
  - build_default_deps binds RetrievalDecision and AnswerVerification on the grader model with bind_structured (D23).
- src/ragdocs/pipelines/agentic/pipeline.py: passes the mode to initial_state. Only when mode == "self_rag" does it copy the graph diagnostics into PipelineResult.diagnostics. The module docstring names the self_rag parent run.
- src/ragdocs/pipelines/registry.py: list_pipelines() is ["baseline", "corrective", "self_rag"], and "self_rag" is AgenticPipeline("self_rag").
- scripts/export_graphs.py: exports corrective and self_rag. docs/graphs/self_rag.mmd is new.
- scripts/decide_probe.py (new, dev-only, not imported by ragdocs): runs decide_retrieval on each eval question. Before each call it waits on the gpt-oss-20b RollingBudget built from cache/budget.json. The budget recorder writes every call to the budget file. Tracing is off. Output goes to cache/decide_probe.jsonl.
- docs/DECISIONS.md: the D26 amendment.
- Tests:
  - tests/test_corrective_mermaid.py (new, written and passing before graph.py changed): the corrective graph from build_graph with fake deps equals corrective.mmd byte for byte.
  - tests/self_rag_fakes.py (new): RaisingChatModel, the decide and verify JSON helpers, fake groq 429, connection and json_validate_failed errors, and SelfRagHarness.
  - tests/test_self_rag_graph.py (new, 28 tests): items (a) to (q) of the prompt, plus the verify message contents, the empty-claims feedback line, the abstain-in-generate path, the recursion threshold, the self_rag Mermaid edges, registration with parent run name "self_rag", and the runtime safety of self_rag_nodes.
  - tests/test_corrective_pipeline.py: the two approved placeholder assertions (Deviations).

Self_rag wiring as built (docs/graphs/self_rag.mmd)
- `__start__ --> decide_retrieval`; `decide_retrieval -.-> retrieve` and `-.-> out_of_scope`; `out_of_scope --> __end__`.
- retrieve, grade_documents, rewrite_query and web_search are wired as in corrective.
- `generate --> verify_answer`; `verify_answer -.-> __end__`, `-.-> regenerate` and `-.-> abstain`; `regenerate -.-> verify_answer` and `-.-> abstain`; `abstain --> __end__`.
- No edge leads from verify_answer or regenerate to retrieve, rewrite_query, grade_documents or decide_retrieval (asserted in test_self_rag_mermaid_has_no_edge_back_to_retrieval).

Decision outcomes (D25 additions, self_rag only; asserted on every tested path)
- decide_retrieval: "ok" when needs_docs is true; "stop" when it is false; "info" on decide_failed.
- out_of_scope: "stop".
- verify_answer:
  - "ok" when grounded and answering.
  - "retry" when not grounded and regenerations < max_regenerations.
  - "stop" when it abstains (not_grounded, does_not_answer).
  - "info" when skipped because the answer abstained, and on verify_failed.
- regenerate: "retry" on success; "stop" on regenerate_failed.
- abstain: "stop".

S2 How to run
- `.venv\Scripts\python scripts\ask.py --pipeline self_rag "question"`.
- `.venv\Scripts\python scripts\export_graphs.py` rewrites both .mmd files.
- `.venv\Scripts\python scripts\decide_probe.py [--limit N]` (live; run the budget check first).

S2 Verification
- Before any S2 code change: `py tasks.py test` gave "320 passed, 1 deselected in 12.25s", including the new corrective Mermaid test.
- Final (2026-11-21, before commit):
  - `py tasks.py lint`: "All checks passed!", "154 files already formatted".
  - `py tasks.py test`: "348 passed, 1 deselected in 14.39s".
- `git diff --stat 8857168 -- tests/ docs/graphs/corrective.mmd results/`: "tests/test_corrective_pipeline.py | 10 ++++++----, 1 file changed, 6 insertions(+), 4 deletions(-)". That diff is only the two approved assertions. corrective.mmd and results/ are unchanged. The new test files are untracked additions.
- Call bound (D27): the worst-case path decide, retrieve, grade, rewrite, retrieve, grade, web_search, generate, verify, regenerate, verify, abstain uses exactly 8 LLM calls: decide 1, grade 2, rewrite 1, generate 2, verify 2. That is 12 node steps.
  - Measured threshold: recursion_limit 13 completes and 12 raises GraphRecursionError. The limit stays 20, which leaves 7 spare steps.
- Budget check before the live calls: `py tasks.py budget --need openai/gpt-oss-20b=62000:70 --need openai/gpt-oss-120b=20000:8 --need gemini-embedding-001=2000:8` reported fits for all three (gpt-oss-20b had 77,504 tokens free at 0.9). Before the smoke asks: `--need openai/gpt-oss-20b=40000:20 --need openai/gpt-oss-120b=20000:8 --need gemini-embedding-001=2000:8` reported fits (118,414 free on gpt-oss-20b after the bucket refilled).

S2 Decide probe (scripts/decide_probe.py, tracing off, 2026-11-21)
- Totals: 50 calls, 20,520 tokens on openai/gpt-oss-20b (mean 410, max 490 on q024), no fallbacks.
- Routing: 49 of 50 routed to retrieval, including all 8 unanswerable items (q043 to q050).
- needs_docs false: one item, q028 (single, answerable), reason "Question about Pregel, not LangGraph." This hit the STOP rule. The human kept the prompt (option 1): Pre-registered expectations item 5, and a Proposed follow-up. The prompt was not changed.
- gpt-oss-20b budget after the probe and the smoke asks: 75,624/200,000 in the token bucket, 104,376 tokens and 892 requests free at 0.9 (`py tasks.py budget`, 2026-11-21 about 07:33 UTC).

S2 Smoke asks (tracing on; `.venv\Scripts\python scripts\ask.py --pipeline self_rag`; started at least 60 s apart, at 07:27:48, 07:29:17, 07:30:33 and 07:32:04 UTC)
- Tokens are per call from cache/budget.json.
- q001 ("My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?"): llm_calls 4. gpt-oss-20b 4,346 tokens (decide 393, grade 1,924, verify 2,029); gpt-oss-120b 1,789. Answered with 2 citations; not abstained; no web.
  - decide_retrieval: "retrieval needed: LangGraph recursion limit question" (ok)
  - retrieve: retrieval event, 5 chunks, hybrid
  - grade_documents: "4 of 5 chunks relevant" (ok); "Route to generate: 4 relevant chunk(s) >= 1" (ok)
  - generate: "Generating from 4 graded excerpts and 0 web results" (info)
  - verify_answer: "answer verified" (ok)
- q009 ("Which channel mechanism avoids storing redundant duplicate states by persisting only incremental changes?"): llm_calls 4. gpt-oss-20b 4,445 tokens (decide 421, grade 1,967, verify 2,057); gpt-oss-120b 2,239. Answered (DeltaChannel) with 2 citations; not abstained.
  - decide_retrieval: "retrieval needed: Asks about LangGraph channel mechanism" (ok)
  - retrieve: 5 chunks
  - grade_documents: "4 of 5 chunks relevant" (ok); "Route to generate: 4 relevant chunk(s) >= 1" (ok)
  - generate: "Generating from 4 graded excerpts and 0 web results" (info)
  - verify_answer: "answer verified" (ok)
- q043 ("Which RetryPolicy argument caps the total wall-clock time ..."; unanswerable): llm_calls 5. gpt-oss-20b 5,498 tokens (decide 453, grade 2,061, rewrite 587, grade 2,397); gpt-oss-120b 957. Abstained (correct for an unanswerable item); used_web True; latency 11,539 ms.
  - decide_retrieval: "retrieval needed: Query about RetryPolicy argument in LangGraph documentation" (ok)
  - retrieve: 5 chunks
  - grade_documents: "0 of 5 chunks relevant" (retry); "Route to rewrite_query: too few relevant chunks; rewrite 1 of 1" (retry)
  - rewrite_query: "query rewritten" (retry)
  - retrieve: 5 chunks
  - grade_documents: "0 of 5 chunks relevant" (retry); "Route to web_search: too few relevant chunks after 1 rewrite(s)" (retry)
  - web_search: "fell back to web search" (retry), 1 web result
  - generate: "Generating from 0 graded excerpts and 1 web results" (info); the generator abstained
  - verify_answer: "verification skipped: abstained" (info)
- "hi, what can you do?": llm_calls 1. gpt-oss-20b 396 tokens (decide). Answer: OUT_OF_SCOPE_TEXT, abstained, no retrieval.
  - decide_retrieval: "no retrieval needed: Greeting, no docs needed" (stop)
  - out_of_scope: "out of scope; answered without retrieval" (stop)
- Smoke totals: gpt-oss-20b 14,685 tokens over 12 calls; gpt-oss-120b 4,985 over 3 calls; gemini-embedding-001 4 retrieval calls.
- No smoke ask reached regenerate or abstain. Their node runs are covered by tests only (c, d, g, j, k).
- After q043, the verify_answer node_end message was changed from "Answer verified" to "Verification finished". The old text was wrong for the skipped and failed cases. q001, q009 and q043 above show the old text; the greeting ask does not reach verify_answer. No test asserts this message.

S2 LangSmith trace check
- The Claude in Chrome browser extension was not connected ("Browser extension is not connected"), so the trace could not be opened in a browser. The nesting was checked instead through the LangSmith API (langsmith Client.list_runs(trace_id=...), read-only, key read through get_settings and configure_tracing, from a scratchpad script).
- q001 trace 01a1fd01-13ef-7551-9ee9-896fd7ce3a0c, 23 runs: self_rag (chain) > graph (chain) > decide_retrieval, retrieve (> hybrid_retrieve, retriever), grade_documents, generate, verify_answer. Each LLM node holds RunnableSequence > ChatGroq + PydanticOutputParser; route_next_step and route_after_grading appear as branch runs. No run nests under one with the same name.
- q009 trace 01a1fd02-7666-73e0-97cb-09f06d74b0a1: the same shape, 23 runs, no same-name nesting.
- q043 trace 01a1fd03-a10b-7662-90fa-7ce0ab75a0f1, 33 runs: self_rag > graph > decide_retrieval, retrieve (> hybrid_retrieve), grade_documents, rewrite_query, retrieve (> hybrid_retrieve), grade_documents, web_search (> tavily_search, tool), generate, verify_answer. No same-name nesting.
- Screenshot: docs/screenshots/langsmith-self-rag-trace.png, taken from the q001 trace by the human (see Deviations).

S2 Decisions made
- The self_rag nodes live in a new module (self_rag_nodes.py), so nodes.py (the corrective nodes) is byte-identical to M10. They reuse nodes._event and nodes._decision.
- The new state keys are NotRequired and set only for self_rag, so the corrective graph's input (and its LangSmith "graph" run inputs) are unchanged.
- regenerate increments regenerations on both success and regenerate_failed (an attempt was made). Fallback names are appended in the order they happen.
- PipelineResult.diagnostics for self_rag is the full graph-state diagnostics (it includes corrective counters such as missing_grades, plus fallbacks and abstain_reason), as the S1 handoff said: "copies graph-state diagnostics into it".
- The decide and verify success messages ("retrieval needed: <reason>", "no retrieval needed: <reason>", "answer verified", "answer not grounded; regenerating", "abstaining: <reason>") and the regenerate message ("regenerating without N unsupported claim(s)") are mine. The prompt fixed only the fallback and skip messages, which are used verbatim.

S2 Deviations from the prompt
- Approved M11 placeholder assertions (human decision, 2026-11-21), in tests/test_corrective_pipeline.py:
  - test_self_rag_not_implemented was renamed to test_self_rag_builds. It now asserts that build_graph("self_rag", fake deps) compiles and contains decide_retrieval, out_of_scope, verify_answer, regenerate and abstain.
  - test_corrective_is_registered expects ["baseline", "corrective", "self_rag"]. Nothing else in that test changed.
- Step 3.3: the browser tool could not connect, so the nesting was checked through the LangSmith API, and the human saved the screenshot.
- Step 2.1: an export test already existed (test_committed_mermaid_matches_fresh_export, through export_mermaid). The new test builds from fake deps and compares bytes, as the prompt asked; the old one is kept unchanged.

S2 Known issues and limitations
- q028 goes out of scope (Pre-registered expectations item 5).
- regenerate and abstain have not been seen in a live trace.
- The verify_answer token figures come from 2 live calls (2,029 and 2,057 tokens, both with 4 contexts); S3 will show the spread.
- The decide probe is one sample per question.

Handoff to S3
- Run commands (each after `py tasks.py budget --need ...` for openai/gpt-oss-20b, openai/gpt-oss-120b and gemini-embedding-001; stop if any need does not fit):
  - `py tasks.py eval --pipeline self_rag`
  - then the judge, `py tasks.py ragas --run-dir <run>` (after `--cache-check`), the experiment and `py tasks.py compare results/runs/baseline-20261116-1050 <run>` (and against corrective-20261120-1852), as in M10 S3.
- Probe token use today (2026-11-21): 20,520 tokens and 50 requests on gpt-oss-20b. The smoke asks added 14,685 tokens and 12 requests on gpt-oss-20b, and 4,985 tokens and 3 requests on gpt-oss-120b.
- Expected quota days:
  - S1 forecast (Pre-registered expectations item 4): 1.9 to 2.5 days on gpt-oss-20b from a drained bucket; plan for 2 to 3 calendar days.
  - S2 measurements lower it. A decide call is about 410 tokens (probe mean), not the 2,301-token stand-in. A verify call was about 2,040 tokens (2 calls).
  - Revised per item: 2,777 + 410 + 1 or 2 x 2,040 = 5,227 to 7,267 tokens. Per 50 items: about 261,000 to 363,000. That is 1 + (261,000 - 180,000) / 200,000 = 1.4 to 1 + (363,000 - 180,000) / 200,000 = 1.9 days.
  - This is an observation from few calls, not a replacement for item 4.
- Watch in S3:
  - 429 retries on worst-case items. The rewrite items (q025, q043 to q050) need about 5,500 grader tokens before verify; with verify they can pass the 7,200 TPM cap at 0.9 within one minute. The throttle and the runner's 429 handling (S1 Step 1d) cover this. The M10 STOP rules still apply: a single call over 7,200 tokens, or two rate-limit failures in a row on one item.
  - Fallback counts: the structured-call fallbacks row (with per-type counts) and structured_output_failures are separate (D26 amendment). Report both, and their sum as the total of failed structured calls.
  - q028: name it beside the first-retrieval hit@5 row and in the false-abstention count (item 5).
  - Items that reach regenerate: check one trace for the regenerate node run, since no smoke ask covered it.

Session 3: evaluation (2026-11-21), in progress
- Step 0: HEAD 558eab0 "M11 (2/3): self-RAG graph and pipeline"; only untracked path docs/audit/ (the documented exception); LANGSMITH_TRACING=true in .env; docs/screenshots/langsmith-self-rag-trace.png exists; no earlier self_rag run folder.
- Baseline run for compare: results/runs/baseline-20261116-1050 (frozen at v1-baseline); corrective run: results/runs/corrective-20261120-1852.
- Budget check (the full forecast of 363,000 tokens on gpt-oss-20b does not fit today: "DOES NOT FIT; fits at 2026-11-22T14:34Z"). Checked the part that can run today instead, as in M10 S3, and relied on the harness pause at the cap: `py tasks.py budget --need openai/gpt-oss-20b=105000:60 --need openai/gpt-oss-120b=130000:50 --need gemini-embedding-001=400:100`: all three "fits".
- `py tasks.py eval --pipeline self_rag` -> run folder results/runs/self_rag-20261121-0744. Paused at the gpt-oss-20b daily cap (175,572/200,000) after 22 items.
- Done: q001 to q022 (per_question.jsonl 22 lines). Remaining (28): q023 to q050.
- Step 1.3 checks on the 22 items: structured-call fallbacks 0; structured_output_failures 0 (failed_attempts empty); error events 0; max LLM calls per item 6 (q006 and q017: both ran verify, regenerate, verify); no item on an out_of_scope path (q028 not yet run).
- This run's tokens (from per_question usage, 22 items): gpt-oss-20b 106,096, gpt-oss-120b 45,815.
- Budget state at 08:16Z (cache/budget.json): gpt-oss-20b 175,552/200,000 (free at 0.9: 4,448); gpt-oss-120b 44,014/200,000; embeddings unchanged. The harness says enough tokens free at 2026-11-21T08:32:17Z (rolling bucket, not UTC midnight); only a few items fit before the next pause, so plan on the rest of the day and possibly the next.

Resume prompt for the next session:
"Continue M11 S3. Read AGENTS.md, docs/progress/PROGRESS.md, docs/progress/M11-self-rag.md (section 'Session 3'). The self_rag run folder is results/runs/self_rag-20261121-0744 (22 of 50 items done). Run `py tasks.py budget --need openai/gpt-oss-20b=<tokens that fit>:<n> --need openai/gpt-oss-120b=...`, then `py tasks.py eval --pipeline self_rag --run-dir results/runs/self_rag-20261121-0744`; on exit 3 update this section and stop. Then continue at Step 1.4 of the S3 prompt (paste summary.md, RAGAS, experiment, compare, screenshot, analysis notes, finish). Do not start a second run folder."

S3 resume 1 (2026-11-22): paused, not at the quota cap
- Budget before resume: gpt-oss-20b 0/200,000 (bucket fully free), gpt-oss-120b 0/200,000, embeddings fine. Ran `py tasks.py eval --pipeline self_rag --run-dir results/runs/self_rag-20261121-0744`; exit 3.
- Items done: 48 of 50 (q001 to q048; per_question.jsonl 48 lines). Remaining: q049, q050.
- Cause of the pause: q049 failed twice at stage grade_documents with BadRequestError, kind structured_output (failed_attempts.jsonl, 2026-11-22T09:36:07Z and 09:37:12Z). This is not a rate limit and not a quota stop: gpt-oss-20b has 129,426/200,000 used, 70,574 free after the run.
- This matches the M10 STOP rule (two failures in a row on one item). Not retried; no second run folder started; nothing else changed.
- Not yet known: the BadRequestError body (the failed_attempts row stores only the class name). Likely candidates to check next session: a structured-output validation rejection from the provider on this item's contexts, or a prompt that is too large for q049. Both are guesses until the error body is read.
- Open question for the human: how to handle q049. Options: (a) rerun the same command once and see whether it repeats; (b) inspect the request for q049 first; (c) record it as a structured-output failure and let the runner continue to q050 (needs your decision under the M10 rule).
- Step 1.4 and later (summary.md, RAGAS, experiment, compare, screenshot, analysis, finish) not started.

S3 resume 1, probe result (2026-11-22)
- Throwaway script cache/q049_probe.py (not committed): same question, retriever first retrieval (5 chunks, 7,232 context chars), GRADE_SYSTEM_PROMPT and GRADE_USER_TEMPLATE, grader gpt-oss-20b via bind_structured (D23 method), one call after budget.wait_for(3,000, 1), budget recorder installed.
- Result: SUCCESS. The call returned a valid GradeBatch with 5 grades, all relevant=False (reasons such as "No mention of Kubernetes Pods or node isolation setting."). No exception, so no error body to show. The failure is intermittent, not deterministic for this input.
- Per the instruction for this case: rerun the same eval command once (q049's third attempt).

S3 resume 1, completion (2026-11-22)
- Reran `py tasks.py eval --pipeline self_rag --run-dir results/runs/self_rag-20261121-0744` once (budget before: gpt-oss-20b 20,000:12, gpt-oss-120b 20,000:6, embeddings 100:4, all fit). Exit 0: "q049 done (3 calls, 3436 ms)", "q050 done (5 calls, 9254 ms)", "All items done. Summary written to results/runs/self_rag-20261121-0744/summary.md". per_question.jsonl holds 50 items; no line written by hand.
- q049 ran as the third attempt in total (resume treatment, as q049 got in corrective in M10). Summary: structured_output_failures 2 (n=50), items with >= 1 failure 1/50 (q049, unanswerable). These two failures stay in the results.
- Summary lines of note (summary.md, judging not yet run: judged 0/38 eligible, so correctness is a lower bound and shows 0): first-retrieval hit@5 0.786 (33/42); false_abstention 0.095 (4/42); abstention_correct 8/8; used_web 7/50; structured-call fallbacks 0/50; error counters all 0; mean llm_calls 4.2; mean tokens per question 6,847; p50 4,824 ms, p95 9,203 ms.
- Not yet done: Step 1.4 onward (judge, RAGAS, experiment, compare, screenshot, analysis notes, finish).
- Pending for Step 4 (analysis_notes.md): q049's grade_documents call hit structured-output failures (BadRequestError, twice) in both corrective and self_rag. Same item, same gpt-oss-20b grader. A probe replay of the identical request succeeded, so it is input-specific but intermittent, not noise and not deterministic.

Proposed follow-ups (S3 resume 1, out of scope)
- failed_attempts.jsonl should store the error code and message (and failed_generation when present), not only the exception class name. Not changed in this session.

S3 Step 1.4a (2026-11-22): first-retrieval hit@5 differences (STOP rule reached)
- Computed with the harness functions (report.first_retrieval_hit_at_5 over judge.load_records) for baseline-20261116-1050, corrective-20261120-1852 and self_rag-20261121-0744, 42 answerable items. Totals: baseline 34, corrective 34, self_rag 33.
- The only answerable item whose first-retrieval hit differs between self_rag and corrective (and baseline) is q028: baseline 1.0, corrective 1.0, self_rag 0.0.
- Evidence: self_rag trace for q028 has no retrieval event: decide_retrieval decision {needs_docs: False, reason "Question about Pregel, not LangGraph.", outcome stop}, then out_of_scope; answer abstained=True with the out-of-scope text. Corrective retrieved 5 chunks (first id 3189f4ab640cb721) and hit.
- No item differs for the other reasons (different chunk ids, cache-fresh embeddings, other): there are none. 41 of 42 items agree across the three runs.
- This is the outcome Pre-registered expectations item 5 predicted (human decision in S2 to keep DECIDE_SYSTEM_PROMPT unchanged). Step 1.4a says to STOP and show the human when an answerable item reaches out_of_scope; stopped here, judging not started.
- cache/s14a.py is the throwaway script (cache/ is not committed).

S3 Step 1.4b (2026-11-22): run summary before judging
- Totals against the S2 forecast: gpt-oss-20b 185,625 in + 58,054 out = 243,679 tokens over 157 calls (S2 revised forecast 261,000 to 363,000 tokens per 50 items; actual is below the low end); gpt-oss-120b 76,926 in + 21,749 out = 98,675 tokens over 53 calls; total 210 calls, 342,354 tokens (262,551 in, 79,803 out). Mean 4.2 calls per item.
- All correctness rows below are NOT YET JUDGED (judged 0/38); the 0.000 values are lower bounds, not results. q028 (answerable, routed out of scope) is a first-retrieval hit@5 miss and one of the false abstentions.

    # Run summary: self_rag-20261121-0744
    
    Pipeline: self_rag. Tracing enabled: True.
    Judge: none, prompt version n/a (source per_question.jsonl), judged 0/38 eligible items.
    WARNING: judging incomplete (38 eligible items unjudged). Correctness fields are lower bounds; run `py tasks.py judge --run-dir <run>`.
    
    Rates are shown as rate (count/n). Correctness uses n = every answerable item;
    a false abstention counts as correctness 0.
    
    ## Overall
    
    | Field | Value |
    |---|---|
    | items | 50 |
    | answerable n | 42 |
    | correct (correctness = 2) | 0.000 (0/42) |
    | correct or partial (correctness >= 1) | 0.000 (0/42) |
    | mean correctness (0-2) | 0.000 (n=42) |
    | citation_support (judged items) | - |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.786 (33/42) |
    | context_hit@5 (on contexts given to the generator) | 0.762 (32/42) |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.679 (n=42) |
    | mean must_mention coverage (soft signal, D15) | 0.857 (n=42) |
    | false_abstention | 0.095 (4/42) |
    | abstention_correct (unanswerable) | 1.000 (8/8) |
    | hallucinated (unanswerable) | 0.000 (0/8) |
    | mean llm_calls | 4.200 (n=50) |
    | p50 latency_ms | 4824 ms |
    | p95 latency_ms | 9203 ms |
    | mean tokens per question | 6847.080 (n=50) |
    | used_web | 0.140 (7/50) |
    | structured_output_failures (failed attempts before success) | 2 (n=50) |
    | items with >= 1 structured_output failure | 0.020 (1/50) |
    | rate-limited attempts (not counted above) | 0 (n=50) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=50) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=50) |
    | unclassified call errors (not counted above) | 0 (n=50) |
    | structured-call fallbacks | 0.000 (0/50) |
    
    ## Per category
    
    | Field | single | multi | version | unanswerable |
    |---|---|---|---|---|
    | items | 28 | 8 | 6 | 8 |
    | answerable n | 28 | 8 | 6 | 0 |
    | correct (correctness = 2) | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | - |
    | correct or partial (correctness >= 1) | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | - |
    | mean correctness (0-2) | 0.000 (n=28) | 0.000 (n=8) | 0.000 (n=6) | - |
    | citation_support (judged items) | - | - | - | - |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.750 (21/28) | 0.875 (7/8) | 0.833 (5/6) | - |
    | context_hit@5 (on contexts given to the generator) | 0.714 (20/28) | 0.875 (7/8) | 0.833 (5/6) | - |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.714 (n=28) | 0.500 (n=8) | 0.750 (n=6) | - |
    | mean must_mention coverage (soft signal, D15) | 0.821 (n=28) | 0.875 (n=8) | 1.000 (n=6) | - |
    | false_abstention | 0.107 (3/28) | 0.125 (1/8) | 0.000 (0/6) | - |
    | abstention_correct (unanswerable) | - | - | - | 1.000 (8/8) |
    | hallucinated (unanswerable) | - | - | - | 0.000 (0/8) |
    | mean llm_calls | 4.036 (n=28) | 4.375 (n=8) | 4.000 (n=6) | 4.750 (n=8) |
    | p50 latency_ms | 4601 ms | 5475 ms | 4741 ms | 8534 ms |
    | p95 latency_ms | 7317 ms | 8070 ms | 5993 ms | 25535 ms |
    | mean tokens per question | 6640.393 (n=28) | 7622.250 (n=8) | 7127.000 (n=6) | 6585.375 (n=8) |
    | used_web | 0.036 (1/28) | 0.000 (0/8) | 0.000 (0/6) | 0.750 (6/8) |
    | structured_output_failures (failed attempts before success) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 2 (n=8) |
    | items with >= 1 structured_output failure | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.125 (1/8) |
    | rate-limited attempts (not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | unclassified call errors (not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | structured-call fallbacks | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.000 (0/8) |
    
    ## Totals (generation)
    
    - Tokens in: 262551; tokens out: 79803; LLM calls: 210; calls without usage data: 0
    - openai/gpt-oss-120b: 76926 in, 21749 out, 53 calls
    - openai/gpt-oss-20b: 185625 in, 58054 out, 157 calls
    - Judge: 0 in, 0 out, 0 calls, 0 cached verdicts

S3 Step 1.5 (2026-11-22): judge
- Budget: `py tasks.py budget --need gemini-3.5-flash-lite=110000:42` fits. `py tasks.py judge --run-dir results/runs/self_rag-20261121-0744`: exit 0, "Judge v2: 0 done, 38 to judge", "Judging complete. Summary written to results/runs/self_rag-20261121-0744/summary.md". The summary was regenerated by the harness. judge_prompt_version 2 (same as baseline and corrective).
- Judged summary.md:

    # Run summary: self_rag-20261121-0744
    
    Pipeline: self_rag. Tracing enabled: True.
    Judge: gemini-3.5-flash-lite, prompt version 2 (source judge_v2.jsonl), judged 38/38 eligible items.
    
    Rates are shown as rate (count/n). Correctness uses n = every answerable item;
    a false abstention counts as correctness 0.
    
    ## Overall
    
    | Field | Value |
    |---|---|
    | items | 50 |
    | answerable n | 42 |
    | correct (correctness = 2) | 0.857 (36/42) |
    | correct or partial (correctness >= 1) | 0.905 (38/42) |
    | mean correctness (0-2) | 1.762 (n=42) |
    | citation_support (judged items) | 0.974 (37/38) |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.786 (33/42) |
    | context_hit@5 (on contexts given to the generator) | 0.762 (32/42) |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.679 (n=42) |
    | mean must_mention coverage (soft signal, D15) | 0.857 (n=42) |
    | false_abstention | 0.095 (4/42) |
    | abstention_correct (unanswerable) | 1.000 (8/8) |
    | hallucinated (unanswerable) | 0.000 (0/8) |
    | mean llm_calls | 4.200 (n=50) |
    | p50 latency_ms | 4824 ms |
    | p95 latency_ms | 9203 ms |
    | mean tokens per question | 6847.080 (n=50) |
    | used_web | 0.140 (7/50) |
    | structured_output_failures (failed attempts before success) | 2 (n=50) |
    | items with >= 1 structured_output failure | 0.020 (1/50) |
    | rate-limited attempts (not counted above) | 0 (n=50) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=50) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=50) |
    | unclassified call errors (not counted above) | 0 (n=50) |
    | structured-call fallbacks | 0.000 (0/50) |
    
    ## Per category
    
    | Field | single | multi | version | unanswerable |
    |---|---|---|---|---|
    | items | 28 | 8 | 6 | 8 |
    | answerable n | 28 | 8 | 6 | 0 |
    | correct (correctness = 2) | 0.857 (24/28) | 0.750 (6/8) | 1.000 (6/6) | - |
    | correct or partial (correctness >= 1) | 0.893 (25/28) | 0.875 (7/8) | 1.000 (6/6) | - |
    | mean correctness (0-2) | 1.750 (n=28) | 1.625 (n=8) | 2.000 (n=6) | - |
    | citation_support (judged items) | 1.000 (25/25) | 0.857 (6/7) | 1.000 (6/6) | - |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.750 (21/28) | 0.875 (7/8) | 0.833 (5/6) | - |
    | context_hit@5 (on contexts given to the generator) | 0.714 (20/28) | 0.875 (7/8) | 0.833 (5/6) | - |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.714 (n=28) | 0.500 (n=8) | 0.750 (n=6) | - |
    | mean must_mention coverage (soft signal, D15) | 0.821 (n=28) | 0.875 (n=8) | 1.000 (n=6) | - |
    | false_abstention | 0.107 (3/28) | 0.125 (1/8) | 0.000 (0/6) | - |
    | abstention_correct (unanswerable) | - | - | - | 1.000 (8/8) |
    | hallucinated (unanswerable) | - | - | - | 0.000 (0/8) |
    | mean llm_calls | 4.036 (n=28) | 4.375 (n=8) | 4.000 (n=6) | 4.750 (n=8) |
    | p50 latency_ms | 4601 ms | 5475 ms | 4741 ms | 8534 ms |
    | p95 latency_ms | 7317 ms | 8070 ms | 5993 ms | 25535 ms |
    | mean tokens per question | 6640.393 (n=28) | 7622.250 (n=8) | 7127.000 (n=6) | 6585.375 (n=8) |
    | used_web | 0.036 (1/28) | 0.000 (0/8) | 0.000 (0/6) | 0.750 (6/8) |
    | structured_output_failures (failed attempts before success) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 2 (n=8) |
    | items with >= 1 structured_output failure | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.125 (1/8) |
    | rate-limited attempts (not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | unclassified call errors (not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |
    | structured-call fallbacks | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.000 (0/8) |
    
    ## Totals (generation)
    
    - Tokens in: 262551; tokens out: 79803; LLM calls: 210; calls without usage data: 0
    - openai/gpt-oss-120b: 76926 in, 21749 out, 53 calls
    - openai/gpt-oss-20b: 185625 in, 58054 out, 157 calls
    - Judge: 65605 in, 2366 out, 37 calls, 1 cached verdicts

S3 Step 2 (2026-11-22): RAGAS and experiment
- `py tasks.py ragas --run-dir ... --cache-check`: 3/41 items fully cached; plan 711 LLM requests (cap at 0.9: 450/day) and 76 embedding requests; still needed about 675 LLM and 74 embedding. `py tasks.py budget --need gemini-3.1-flash-lite=470000:400 --need gemini-embedding-001=2000:80` fits (0/500 used; M10 actual use for the same metrics was 367 requests and 461,056 tokens, so one day).
- `py tasks.py ragas --run-dir results/runs/self_rag-20261121-0744`: exit 0 in one session. "Wrote ragas_config.json, ragas_scores.jsonl, ragas_summary.json". n_errored 0 on all four metrics (faithfulness 38/38 mean 0.934, response_relevancy 38/38 mean 0.819, context_precision 41/41 mean 0.786, context_recall 41/41 mean 0.817). The 10% error STOP rule was not reached.
- `py tasks.py experiment --run-dir results/runs/self_rag-20261121-0744`: exit 0, "Dataset ragdocs-eval-set-v1 verified (same 50 ids and sha256)"; experiment self_rag-20261121-0744, id 902633a2-70f8-4bc5-81a5-56bde62733e7, 50 examples, current.
  - URL: https://smith.langchain.com/o/dc790a75-743f-467d-a940-18bb085de125/datasets/6f229f5d-8cff-45b9-840f-3ec576feb329/compare?selectedSessions=902633a2-70f8-4bc5-81a5-56bde62733e7

S3 Step 3 (2026-11-22): compare
- `py tasks.py compare results/runs/baseline-20261116-1050 results/runs/corrective-20261120-1852 results/runs/self_rag-20261121-0744`: exit 0, accepted. Baseline run is the one M10 compared against (frozen at v1-baseline).
- structured_output_failures side by side, S1 old (stored) against new (compare output): baseline-20261116-1050 0 and 0; corrective-20261120-1852 2 (old) and 1 (new, q049 override: its failure is a structured-output one reclassified, q043 reclassified to transient); self_rag-20261121-0744 2 (no override; q049 grade_documents twice).
- Changed questions against baseline: corrective q024 (1 -> 0) and q034 (2 -> 1); self_rag q028 (2 -> 0, abstained) and q033 (2 -> 1). Paired verdicts: all "no measurable difference" for both pipelines against baseline.
- results/summary.md as written:

    # Run comparison
    
    Judge gemini-3.5-flash-lite, prompt version 2. Rates are rate (count/n); correctness n = every answerable item.
    
    ## Overall
    
    | Field | baseline-20261116-1050 | corrective-20261120-1852 | self_rag-20261121-0744 |
    |---|---|---|---|
    | items | 50 | 50 | 50 |
    | answerable n | 42 | 42 | 42 |
    | correct (correctness = 2) | 0.905 (38/42) | 0.881 (37/42) | 0.857 (36/42) |
    | correct or partial (correctness >= 1) | 0.929 (39/42) | 0.905 (38/42) | 0.905 (38/42) |
    | mean correctness (0-2) | 1.833 (n=42) | 1.786 (n=42) | 1.762 (n=42) |
    | citation_support (judged items) | 1.000 (39/39) | 0.949 (37/39) | 0.974 (37/38) |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.810 (34/42) | 0.810 (34/42) | 0.786 (33/42) |
    | context_hit@5 (on contexts given to the generator) | 0.810 (34/42) | 0.786 (33/42) | 0.762 (32/42) |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.726 (n=42) | 0.702 (n=42) | 0.679 (n=42) |
    | mean must_mention coverage (soft signal, D15) | 0.905 (n=42) | 0.905 (n=42) | 0.857 (n=42) |
    | false_abstention | 0.071 (3/42) | 0.071 (3/42) | 0.095 (4/42) |
    | abstention_correct (unanswerable) | 1.000 (8/8) | 1.000 (8/8) | 1.000 (8/8) |
    | hallucinated (unanswerable) | 0.000 (0/8) | 0.000 (0/8) | 0.000 (0/8) |
    | mean llm_calls | 1.000 (n=50) | 2.320 (n=50) | 4.200 (n=50) |
    | p50 latency_ms | 2208 ms | 3167 ms | 4824 ms |
    | p95 latency_ms | 3734 ms | 8002 ms | 9203 ms |
    | mean tokens per question | 2333.560 (n=50) | 4577.300 (n=50) | 6847.080 (n=50) |
    | used_web | 0.000 (0/50) | 0.160 (8/50) | 0.140 (7/50) |
    | structured_output_failures (failed attempts before success) | 0 (n=50) | 1 (n=50) | 2 (n=50) |
    | items with >= 1 structured_output failure | 0.000 (0/50) | 0.020 (1/50) | 0.020 (1/50) |
    | rate-limited attempts (not counted above) | 10 (n=50) | 0 (n=50) | 0 (n=50) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=50) | 1 (n=50) | 0 (n=50) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=50) | 0 (n=50) | 0 (n=50) |
    | unclassified call errors (not counted above) | 0 (n=50) | 0 (n=50) | 0 (n=50) |
    | structured-call fallbacks | 0.000 (0/50) | 0.000 (0/50) | 0.000 (0/50) |
    | RAGAS faithfulness (prose-level grounding signal) | 0.922 (39) | 0.909 (39) | 0.934 (38) |
    | RAGAS response_relevancy | 0.813 (39) | 0.823 (39) | 0.819 (38) |
    | RAGAS context_precision (on contexts given to the generator) | 0.720 (42) | 0.781 (42) | 0.786 (41) |
    | RAGAS context_recall (on contexts given to the generator) | 0.845 (42) | 0.821 (42) | 0.817 (41) |
    
    - Note: corrective-20261120-1852 q043: failed-attempt kind set to transient by results/error_reclassifications.json (the stored message cannot show it). Evidence: docs/progress/M10-corrective-rag.md, section 'S3 Step 1: eval run', failed attempts, q043: LangSmith tavily_search run gives 'Tavily search failed after 1 attempt(s): ConnectionError (status None)'; LangSmith run id 01a1fa8c-234c-7460-9f93-b2217c3a89d1 (per_question.jsonl langsmith_run_id; the eval_item run of the attempt that succeeded).
    - Note: corrective-20261120-1852 q049: failed-attempt kind set to structured_output by results/error_reclassifications.json (the stored message cannot show it). Evidence: docs/progress/M10-corrective-rag.md, section 'S3 additional facts', item 3) q049: Groq 400, type invalid_request_error, code json_validate_failed, on rewrite_query's structured RewrittenQuery call; LangSmith run id 01a1fa93-2f8a-7913-b630-4147fc269192 (per_question.jsonl langsmith_run_id; the eval_item run of the attempt that succeeded).
    
    ## single
    
    | Field | baseline-20261116-1050 | corrective-20261120-1852 | self_rag-20261121-0744 |
    |---|---|---|---|
    | items | 28 | 28 | 28 |
    | answerable n | 28 | 28 | 28 |
    | correct (correctness = 2) | 0.893 (25/28) | 0.893 (25/28) | 0.857 (24/28) |
    | correct or partial (correctness >= 1) | 0.929 (26/28) | 0.893 (25/28) | 0.893 (25/28) |
    | mean correctness (0-2) | 1.821 (n=28) | 1.786 (n=28) | 1.750 (n=28) |
    | citation_support (judged items) | 1.000 (26/26) | 0.962 (25/26) | 1.000 (25/25) |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.786 (22/28) | 0.786 (22/28) | 0.750 (21/28) |
    | context_hit@5 (on contexts given to the generator) | 0.786 (22/28) | 0.750 (21/28) | 0.714 (20/28) |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.786 (n=28) | 0.750 (n=28) | 0.714 (n=28) |
    | mean must_mention coverage (soft signal, D15) | 0.893 (n=28) | 0.893 (n=28) | 0.821 (n=28) |
    | false_abstention | 0.071 (2/28) | 0.071 (2/28) | 0.107 (3/28) |
    | abstention_correct (unanswerable) | - | - | - |
    | hallucinated (unanswerable) | - | - | - |
    | mean llm_calls | 1.000 (n=28) | 2.071 (n=28) | 4.036 (n=28) |
    | p50 latency_ms | 2062 ms | 2942 ms | 4601 ms |
    | p95 latency_ms | 3447 ms | 6515 ms | 7317 ms |
    | mean tokens per question | 2399.107 (n=28) | 4311.429 (n=28) | 6640.393 (n=28) |
    | used_web | 0.000 (0/28) | 0.036 (1/28) | 0.036 (1/28) |
    | structured_output_failures (failed attempts before success) | 0 (n=28) | 0 (n=28) | 0 (n=28) |
    | items with >= 1 structured_output failure | 0.000 (0/28) | 0.000 (0/28) | 0.000 (0/28) |
    | rate-limited attempts (not counted above) | 10 (n=28) | 0 (n=28) | 0 (n=28) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=28) | 0 (n=28) | 0 (n=28) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=28) | 0 (n=28) | 0 (n=28) |
    | unclassified call errors (not counted above) | 0 (n=28) | 0 (n=28) | 0 (n=28) |
    | structured-call fallbacks | 0.000 (0/28) | 0.000 (0/28) | 0.000 (0/28) |
    | RAGAS faithfulness (prose-level grounding signal) | 0.908 (26) | 0.922 (26) | 0.949 (25) |
    | RAGAS response_relevancy | 0.818 (26) | 0.827 (26) | 0.828 (25) |
    | RAGAS context_precision (on contexts given to the generator) | 0.772 (28) | 0.848 (28) | 0.858 (27) |
    | RAGAS context_recall (on contexts given to the generator) | 0.857 (28) | 0.857 (28) | 0.852 (27) |
    
    ## multi
    
    | Field | baseline-20261116-1050 | corrective-20261120-1852 | self_rag-20261121-0744 |
    |---|---|---|---|
    | items | 8 | 8 | 8 |
    | answerable n | 8 | 8 | 8 |
    | correct (correctness = 2) | 0.875 (7/8) | 0.750 (6/8) | 0.750 (6/8) |
    | correct or partial (correctness >= 1) | 0.875 (7/8) | 0.875 (7/8) | 0.875 (7/8) |
    | mean correctness (0-2) | 1.750 (n=8) | 1.625 (n=8) | 1.625 (n=8) |
    | citation_support (judged items) | 1.000 (7/7) | 0.857 (6/7) | 0.857 (6/7) |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.875 (7/8) | 0.875 (7/8) | 0.875 (7/8) |
    | context_hit@5 (on contexts given to the generator) | 0.875 (7/8) | 0.875 (7/8) | 0.875 (7/8) |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.500 (n=8) | 0.500 (n=8) | 0.500 (n=8) |
    | mean must_mention coverage (soft signal, D15) | 0.875 (n=8) | 0.875 (n=8) | 0.875 (n=8) |
    | false_abstention | 0.125 (1/8) | 0.125 (1/8) | 0.125 (1/8) |
    | abstention_correct (unanswerable) | - | - | - |
    | hallucinated (unanswerable) | - | - | - |
    | mean llm_calls | 1.000 (n=8) | 2.000 (n=8) | 4.375 (n=8) |
    | p50 latency_ms | 2772 ms | 3692 ms | 5475 ms |
    | p95 latency_ms | 3610 ms | 4243 ms | 8070 ms |
    | mean tokens per question | 2368.500 (n=8) | 4351.125 (n=8) | 7622.250 (n=8) |
    | used_web | 0.000 (0/8) | 0.000 (0/8) | 0.000 (0/8) |
    | structured_output_failures (failed attempts before success) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | items with >= 1 structured_output failure | 0.000 (0/8) | 0.000 (0/8) | 0.000 (0/8) |
    | rate-limited attempts (not counted above) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | unclassified call errors (not counted above) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | structured-call fallbacks | 0.000 (0/8) | 0.000 (0/8) | 0.000 (0/8) |
    | RAGAS faithfulness (prose-level grounding signal) | 0.907 (7) | 0.827 (7) | 0.938 (7) |
    | RAGAS response_relevancy | 0.817 (7) | 0.843 (7) | 0.813 (7) |
    | RAGAS context_precision (on contexts given to the generator) | 0.479 (8) | 0.500 (8) | 0.500 (8) |
    | RAGAS context_recall (on contexts given to the generator) | 0.688 (8) | 0.562 (8) | 0.562 (8) |
    
    ## version
    
    | Field | baseline-20261116-1050 | corrective-20261120-1852 | self_rag-20261121-0744 |
    |---|---|---|---|
    | items | 6 | 6 | 6 |
    | answerable n | 6 | 6 | 6 |
    | correct (correctness = 2) | 1.000 (6/6) | 1.000 (6/6) | 1.000 (6/6) |
    | correct or partial (correctness >= 1) | 1.000 (6/6) | 1.000 (6/6) | 1.000 (6/6) |
    | mean correctness (0-2) | 2.000 (n=6) | 2.000 (n=6) | 2.000 (n=6) |
    | citation_support (judged items) | 1.000 (6/6) | 1.000 (6/6) | 1.000 (6/6) |
    | first-retrieval hit@5 (like-for-like retrieval) | 0.833 (5/6) | 0.833 (5/6) | 0.833 (5/6) |
    | context_hit@5 (on contexts given to the generator) | 0.833 (5/6) | 0.833 (5/6) | 0.833 (5/6) |
    | mean context_evidence_recall@5 (on contexts given to the generator) | 0.750 (n=6) | 0.750 (n=6) | 0.750 (n=6) |
    | mean must_mention coverage (soft signal, D15) | 1.000 (n=6) | 1.000 (n=6) | 1.000 (n=6) |
    | false_abstention | 0.000 (0/6) | 0.000 (0/6) | 0.000 (0/6) |
    | abstention_correct (unanswerable) | - | - | - |
    | hallucinated (unanswerable) | - | - | - |
    | mean llm_calls | 1.000 (n=6) | 2.000 (n=6) | 4.000 (n=6) |
    | p50 latency_ms | 2430 ms | 3047 ms | 4741 ms |
    | p95 latency_ms | 3420 ms | 3816 ms | 5993 ms |
    | mean tokens per question | 2352.833 (n=6) | 4441.333 (n=6) | 7127.000 (n=6) |
    | used_web | 0.000 (0/6) | 0.000 (0/6) | 0.000 (0/6) |
    | structured_output_failures (failed attempts before success) | 0 (n=6) | 0 (n=6) | 0 (n=6) |
    | items with >= 1 structured_output failure | 0.000 (0/6) | 0.000 (0/6) | 0.000 (0/6) |
    | rate-limited attempts (not counted above) | 0 (n=6) | 0 (n=6) | 0 (n=6) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=6) | 0 (n=6) | 0 (n=6) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=6) | 0 (n=6) | 0 (n=6) |
    | unclassified call errors (not counted above) | 0 (n=6) | 0 (n=6) | 0 (n=6) |
    | structured-call fallbacks | 0.000 (0/6) | 0.000 (0/6) | 0.000 (0/6) |
    | RAGAS faithfulness (prose-level grounding signal) | 1.000 (6) | 0.948 (6) | 0.868 (6) |
    | RAGAS response_relevancy | 0.784 (6) | 0.778 (6) | 0.788 (6) |
    | RAGAS context_precision (on contexts given to the generator) | 0.798 (6) | 0.847 (6) | 0.847 (6) |
    | RAGAS context_recall (on contexts given to the generator) | 1.000 (6) | 1.000 (6) | 1.000 (6) |
    
    ## unanswerable
    
    | Field | baseline-20261116-1050 | corrective-20261120-1852 | self_rag-20261121-0744 |
    |---|---|---|---|
    | items | 8 | 8 | 8 |
    | answerable n | 0 | 0 | 0 |
    | correct (correctness = 2) | - | - | - |
    | correct or partial (correctness >= 1) | - | - | - |
    | mean correctness (0-2) | - | - | - |
    | citation_support (judged items) | - | - | - |
    | first-retrieval hit@5 (like-for-like retrieval) | - | - | - |
    | context_hit@5 (on contexts given to the generator) | - | - | - |
    | mean context_evidence_recall@5 (on contexts given to the generator) | - | - | - |
    | mean must_mention coverage (soft signal, D15) | - | - | - |
    | false_abstention | - | - | - |
    | abstention_correct (unanswerable) | 1.000 (8/8) | 1.000 (8/8) | 1.000 (8/8) |
    | hallucinated (unanswerable) | 0.000 (0/8) | 0.000 (0/8) | 0.000 (0/8) |
    | mean llm_calls | 1.000 (n=8) | 3.750 (n=8) | 4.750 (n=8) |
    | p50 latency_ms | 1822 ms | 6638 ms | 8534 ms |
    | p95 latency_ms | 4181 ms | 8706 ms | 25535 ms |
    | mean tokens per question | 2054.750 (n=8) | 5836.000 (n=8) | 6585.375 (n=8) |
    | used_web | 0.000 (0/8) | 0.875 (7/8) | 0.750 (6/8) |
    | structured_output_failures (failed attempts before success) | 0 (n=8) | 1 (n=8) | 2 (n=8) |
    | items with >= 1 structured_output failure | 0.000 (0/8) | 0.125 (1/8) | 0.125 (1/8) |
    | rate-limited attempts (not counted above) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | transient call errors (connection, timeout, 5xx; not counted above) | 0 (n=8) | 1 (n=8) | 0 (n=8) |
    | permanent call errors (auth, plan limit, other 4xx; not counted above) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | unclassified call errors (not counted above) | 0 (n=8) | 0 (n=8) | 0 (n=8) |
    | structured-call fallbacks | 0.000 (0/8) | 0.000 (0/8) | 0.000 (0/8) |
    | RAGAS faithfulness (prose-level grounding signal) | - | - | - |
    | RAGAS response_relevancy | - | - | - |
    | RAGAS context_precision (on contexts given to the generator) | - | - | - |
    | RAGAS context_recall (on contexts given to the generator) | - | - | - |
    
    ## Changed questions (against baseline-20261116-1050)
    
    ### corrective-20261120-1852
    
    - q024: correctness 1 -> 0 (worse)
    - q034: correctness 2 -> 1 (worse)
    
    ### self_rag-20261121-0744
    
    - q028: correctness 2 -> 0 (worse); abstained False -> True
    - q033: correctness 2 -> 1 (worse)
    
    
    ## Paired
    
    Means over items scored in every compared run (n). A paired item is better or worse when the difference exceeds 0.2; the verdict is "no measurable difference" unless wins minus losses is 3 or more (D19).
    
    ### corrective-20261120-1852 against baseline-20261116-1050
    
    **Correctness verdict (primary): no measurable difference.** 0 items better, 2 worse, 40 unchanged, out of 42 answerable items (a direction needs a net of 3 items). The correctness row in the table is supporting detail; must_mention coverage is a soft signal (D15).
    
    | Metric | n | first mean | this mean | better | worse | verdict |
    |---|---|---|---|---|---|---|
    | correctness (0-2; abstained = 0) | 42 | 1.833 | 1.786 | 0 | 2 | no measurable difference |
    | context_evidence_recall@5 (on contexts given to the generator) | 42 | 0.726 | 0.702 | 0 | 1 | no measurable difference |
    | must_mention coverage (soft signal, D15) | 42 | 0.905 | 0.905 | 0 | 0 | no measurable difference |
    | RAGAS faithfulness (prose-level grounding signal) | 38 | 0.929 | 0.916 | 2 | 3 | no measurable difference |
    | RAGAS response_relevancy | 38 | 0.811 | 0.821 | 1 | 0 | no measurable difference |
    | RAGAS context_precision (on contexts given to the generator) | 41 | 0.731 | 0.776 | 2 | 1 | no measurable difference |
    | RAGAS context_recall (on contexts given to the generator) | 41 | 0.841 | 0.817 | 0 | 1 | no measurable difference |
    
    ### self_rag-20261121-0744 against baseline-20261116-1050
    
    **Correctness verdict (primary): no measurable difference.** 0 items better, 2 worse, 40 unchanged, out of 42 answerable items (a direction needs a net of 3 items). The correctness row in the table is supporting detail; must_mention coverage is a soft signal (D15).
    
    | Metric | n | first mean | this mean | better | worse | verdict |
    |---|---|---|---|---|---|---|
    | correctness (0-2; abstained = 0) | 42 | 1.833 | 1.762 | 0 | 2 | no measurable difference |
    | context_evidence_recall@5 (on contexts given to the generator) | 42 | 0.726 | 0.679 | 0 | 2 | no measurable difference |
    | must_mention coverage (soft signal, D15) | 42 | 0.905 | 0.857 | 0 | 2 | no measurable difference |
    | RAGAS faithfulness (prose-level grounding signal) | 38 | 0.929 | 0.934 | 3 | 4 | no measurable difference |
    | RAGAS response_relevancy | 38 | 0.811 | 0.819 | 1 | 0 | no measurable difference |
    | RAGAS context_precision (on contexts given to the generator) | 41 | 0.731 | 0.786 | 2 | 0 | no measurable difference |
    | RAGAS context_recall (on contexts given to the generator) | 41 | 0.841 | 0.817 | 0 | 1 | no measurable difference |

S3 Steps 3.3, 4 and 5 (2026-11-22)
- Screenshot docs/screenshots/langsmith-three-way-comparison.png saved by the human (columns set in the LangSmith comparison view for baseline-20261116-1050-r2, corrective-20261120-1852 and self_rag-20261121-0744; shows citation_support, context_hit_at_5, context_precision, context_recall, correctness, faithfulness, first_retrieval_hit_at_5, response_relevancy). File exists, 167,759 bytes.
- results/analysis_notes.md written from committed files. Correction to the S3 instruction for the q049 line: in corrective, the q049 structured-output failure was at rewrite_query (Groq 400 json_validate_failed, per results/error_reclassifications.json evidence), not at grade_documents. In self_rag it was at grade_documents (BadRequestError, body not stored). The note says this. Both are the same item on the same gpt-oss-20b grader; the replay probe of the self_rag request succeeded.
- Verification: `py tasks.py lint`: "All checks passed!", "154 files already formatted". `py tasks.py test`: "348 passed, 1 deselected in 21.93s".

Proposed follow-ups (S3, out of scope)
- failed_attempts.jsonl should store the error code, message and failed_generation (when present), not only the exception class name.
- Router miss: decide_retrieval read Pregel (LangGraph's own runtime) as out of scope (q028, reason "Question about Pregel, not LangGraph."). Possible fixes: name LangGraph internals (Pregel, channels, checkpointers) in DECIDE_SYSTEM_PROMPT, or retrieve first and route out of scope only when retrieval scores are low. Not applied in M11, because tuning on the eval set would invalidate it. The live demo in M12 to M14 will behave the same way on similar questions.
