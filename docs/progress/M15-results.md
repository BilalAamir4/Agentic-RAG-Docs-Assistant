# M15: Results and write-up

Status: Done
Date: 2026-11-23

## Goal

Session 1 of 2: generators and the failure review, no prose. Done here: README results block generator (`py tasks.py readme [--check]`, CI step), `results/failure_labels.csv` and `results/failure_review.md`. S2 writes the README prose and releases.

## What was built

- `src/ragdocs/eval/format.py`: fmt_rate, fmt_mean, fmt_calls, fmt_tokens, fmt_ms_as_s, fmt_percent, to_fixed; return "n/a" for None; match `web/src/lib/format.ts` (ties round up through Decimal, as JavaScript does).
- `src/ragdocs/eval/compare.py`: new `count_verdict(base, other, margin)` (see Step 1d; no existing logic moved).
- `src/ragdocs/config.py`: new `Settings.rerank_gate_min_gain = 3` (the D6 gate threshold, previously only prose).
- `src/ragdocs/eval/readme_results.py`: builds the block from summarize, the compare functions, the retrieval run, the index manifest, judge_audit.md and ragas_config.json; marker replace and check logic.
- `scripts/render_readme_results.py`: thin CLI, `--write` (default) and `--check`.
- `src/ragdocs/eval/failure_review.py` and `scripts/failure_breakdown.py`: labels, CSV and review file.
- `tasks.py`: new command `readme [--check]`; nothing else changed.
- `.github/workflows/ci.yml`: step "README results block is up to date" (`python tasks.py readme --check`) after "Test", both operating systems; nothing else changed.
- `README.md`: did not exist; created with only `## Results`, the two markers and the block.
- `results/failure_labels.csv`, `results/failure_review.md`: generated.
- Tests: `tests/test_eval_format.py`, `tests/test_failure_review.py`, `tests/test_readme_results.py`. No existing test file was edited.

## How to run

```
py tasks.py readme            # rewrite the block in README.md
py tasks.py readme --check    # exit 1 with a diff if stale or markers missing
.venv\Scripts\python scripts\failure_breakdown.py    # rewrite the CSV and review file
```

## Verification

```
py tasks.py lint   -> All checks passed! / 185 files already formatted
py tasks.py test   -> 525 passed, 1 deselected in 26.98s
py tasks.py readme --check -> README results block is up to date.
py tasks.py web-test -> Test Files  10 passed (10); Tests  71 passed (71)
```

- `git diff e8d8f52 -- src/ragdocs/pipelines src/ragdocs/api requirements.txt requirements-dev.txt api/index.py vercel.json web/src public/` is empty. `git status --short results/runs` is empty (44 tracked files unchanged).
- `py tasks.py compare <baseline> <corrective> <self_rag>` rerun: `git diff results/summary.md` is empty.
- failure_breakdown run twice: CSV and review file byte-identical (cmp). No CR characters in README.md, the CSV or the review file.
- The paired verdicts in the README equal results/analysis_notes.md section 4 for all three pairs (for example corrective vs baseline faithfulness 2 wins / 3 losses, self_rag vs corrective 4 / 3).

### Step 1 findings

a) Run folders (names from the header row of results/summary.md): `results/runs/baseline-20261116-1050`, `results/runs/corrective-20261120-1852`, `results/runs/self_rag-20261121-0744`. Other folders: `baseline-20261116-0919` (judge v1 only, not comparable) and `retrieval-20261025`. M11 figures confirmed (results/summary.md and the rendered block): correct 38/37/36 of 42; mean tokens 2,334 / 4,577 / 6,847; p95 3,734 / 8,002 / 9,203 ms; web search 0 / 8 / 7 of 50. compare takes no output path, so I reran it for real and confirmed summary.md is byte-identical.

b) Retrieval ablation `results/runs/retrieval-20261025`: files config.json, per_question.jsonl, table.md. per_question.jsonl rows hold, per mode (dense, bm25, hybrid, hybrid_rerank): hit_at_1, hit_at_5, mrr, evidence_recall_at_5, retrieved[]; plus candidate_hit_at_20. The aggregation existed only in scripts/eval_retrieval.py (table.md); `readme_results.ablation_stats` re-sums per_question.jsonl and reproduces table.md (hit@1/hit@5: dense 22/35, bm25 11/25, hybrid 22/34, hybrid_rerank 17/35; hit@20 39/42). D6 gate: hybrid hit@5 34/42 to hybrid_rerank 35/42 (gain 1, gate 3), hit@1 22/42 to 17/42: FAIL, as in D6.

c) Provenance: eval set 50 items (42 answerable, 8 unanswerable), tag `eval-set-v1` (commit c92688d), sha256 `316b1d683050e426ad5bf2324b9ca7211d30ea2566276320489e6acb538a470f` (matches the file and the run configs). Corpus: https://github.com/langchain-ai/docs commit `a6e223d2f67558caa20589a03443e918b582943b` (data/index/manifest.json `source_commit`, also data/processed/source.json `commit`; 41 pages, 553 chunks). Judge gemini-3.5-flash-lite, effective prompt version 2 (judge_v2.jsonl). Judge audit (D9, `scripts/judge_audit.py --score`, run baseline-20261116-1050): correctness 10/11, citation_support 11/11, gate PASS, disagreement q031. RAGAS 0.4.4 with LLM gemini-3.1-flash-lite (ragas_config.json). M09 sanity check: failed, faithfulness 0.896 on the 8 items labelled faithful against 0.963 on the 3 labelled not faithful (D19 update); presentation rule: "prose-level grounding signal".

d) Paired view and noise verdicts: the paired logic was already in functions (ragdocs.eval.compare), not inline in the script. The count verdict did not exist in code (analysis_notes.md section 4 was computed by hand, wording "none" / "measurable (+N)"), so I added `ragdocs.eval.compare.count_verdict`. Reused unchanged: `item_values`, `paired_compare`, `noise_verdict`, `PairedResult`, `check_comparable`, `NO_DIFFERENCE`, `PAIRED_METRICS`. Nothing was moved. The count margin reuses `Settings.compare_noise_margin` (3).

e) export_results.py maps through its `METRICS` list (key, label, kind, unit, summarize overall field). The README rows use the same fields: correct, correct_or_partial, citation_support, abstention_correct, hallucinated, first_retrieval_hit@5, context_hit@5, ragas_faithfulness, ragas_response_relevancy, ragas_context_precision, ragas_context_recall, mean_llm_calls, mean_tokens_per_question, latency_ms_p50. README-only fields: false_abstention, used_web, latency_ms_p95 (all exist in summarize). A test compares the two lists.

f) How runs record each case, with an example id from the committed runs:
- answerable routed out_of_scope: a `decision` event on node `out_of_scope` after `decide_retrieval` (needs_docs false), no retrieval event. Example: self_rag q028.
- failed structured call: FailedAttempt with kind `structured_output` (per_question.jsonl failed_attempts, failed_attempts.jsonl). Examples: self_rag q049 (two grade_documents attempts), corrective q049 (kind set by results/error_reclassifications.json). Self-RAG fallbacks go to `result.diagnostics["fallbacks"]` (D26 amendment): no committed item has one (self_rag diagnostics hold only the grading and citation counters, all 0, plus web_duplicates_dropped on 7 items). Baseline and corrective have no diagnostics.
- used_web: `result.used_web` and `scores.used_web`. Examples: corrective q043, self_rag q025.
- first retrieval event: first trace event of type `retrieval`, data.chunks with chunk_id and url (baseline: url only, so its value comes from its contexts, D22). Example: self_rag q006. No retrieval event: self_rag q028.

g) README.md did not exist.

h) Badge URL form (https://docs.github.com/en/actions/how-tos/monitor-workflows/add-a-status-badge): `https://github.com/OWNER/REPOSITORY/actions/workflows/WORKFLOW-FILE/badge.svg`, optional `?branch=NAME` and `?event=push`; the page gives no link target. For this repo (owner and name from the origin remote): `https://github.com/BilalAamir4/Agentic-RAG-Docs-Assistant/actions/workflows/ci.yml/badge.svg`. Mermaid (https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams): "Diagram rendering is available in GitHub Issues, GitHub Discussions, pull requests, wikis, and Markdown files"; use a fenced block with language `mermaid`. Existing sources: docs/graphs/corrective.mmd and self_rag.mmd.

## Rendered README block (as committed)

````
Generated by `py tasks.py readme` from committed files in `results/`; do not edit between the markers.

### Main results

50 questions (42 answerable, 8 unanswerable).

| Metric | Baseline RAG | Corrective RAG | Self-RAG |
|---|---|---|---|
| Correct answers | 90.5% (38/42) | 88.1% (37/42) | 85.7% (36/42) |
| Correct or partial | 92.9% (39/42) | 90.5% (38/42) | 90.5% (38/42) |
| Citation support | 100.0% (39/39) | 94.9% (37/39) | 97.4% (37/38) |
| Unanswerable correctly declined | 100.0% (8/8) | 100.0% (8/8) | 100.0% (8/8) |
| Hallucinated on unanswerable | 0.0% (0/8) | 0.0% (0/8) | 0.0% (0/8) |
| False abstentions | 7.1% (3/42) | 7.1% (3/42) | 9.5% (4/42) |
| First-retrieval hit@5 (like-for-like retrieval) | 81.0% (34/42) | 81.0% (34/42) | 78.6% (33/42) |
| Context hit@5 (on contexts given to the generator) | 81.0% (34/42) | 78.6% (33/42) | 76.2% (32/42) |
| RAGAS faithfulness | 0.92 (n=39) | 0.91 (n=39) | 0.93 (n=38) |
| RAGAS response relevancy | 0.81 (n=39) | 0.82 (n=39) | 0.82 (n=38) |
| RAGAS context precision (on contexts given to the generator) | 0.72 (n=42) | 0.78 (n=42) | 0.79 (n=41) |
| RAGAS context recall (on contexts given to the generator) | 0.85 (n=42) | 0.82 (n=42) | 0.82 (n=41) |
| Web search used | 0.0% (0/50) | 16.0% (8/50) | 14.0% (7/50) |
| Mean LLM calls per question | 1.0 | 2.3 | 4.2 |
| Mean tokens per question | 2,334 | 4,577 | 6,847 |
| Median latency | 2.2 s | 3.2 s | 4.8 s |
| p95 latency | 3.7 s | 8.0 s | 9.2 s |

### Is the difference real?

Counts: a difference under 3 questions is "no measurable difference" (D19). RAGAS: a paired item is a win or loss when its score differs by more than 0.2; the verdict needs wins minus losses of at least 3, over the items scored in all three runs. Citation support counts judged items, and the judged n differs between runs.

#### Corrective RAG vs Baseline RAG

| Count metric | Baseline RAG | Corrective RAG | Difference (questions) | Verdict |
|---|---|---|---|---|
| Correct answers | 38 | 37 | -1 | no measurable difference |
| Correct or partial | 39 | 38 | -1 | no measurable difference |
| Citation support | 39 | 37 | -2 | no measurable difference |
| Unanswerable correctly declined | 8 | 8 | 0 | no measurable difference |
| Hallucinated on unanswerable | 0 | 0 | 0 | no measurable difference |
| False abstentions | 3 | 3 | 0 | no measurable difference |
| First-retrieval hit@5 (like-for-like retrieval) | 34 | 34 | 0 | no measurable difference |
| Context hit@5 (on contexts given to the generator) | 34 | 33 | -1 | no measurable difference |
| Web search used | 0 | 8 | +8 | measurable (+8) |

| RAGAS metric | Paired n | Wins | Losses | Verdict |
|---|---|---|---|---|
| RAGAS faithfulness (prose-level grounding signal) | 38 | 2 | 3 | no measurable difference |
| RAGAS response_relevancy | 38 | 1 | 0 | no measurable difference |
| RAGAS context_precision (on contexts given to the generator) | 41 | 2 | 1 | no measurable difference |
| RAGAS context_recall (on contexts given to the generator) | 41 | 0 | 1 | no measurable difference |

#### Self-RAG vs Baseline RAG

| Count metric | Baseline RAG | Self-RAG | Difference (questions) | Verdict |
|---|---|---|---|---|
| Correct answers | 38 | 36 | -2 | no measurable difference |
| Correct or partial | 39 | 38 | -1 | no measurable difference |
| Citation support | 39 | 37 | -2 | no measurable difference |
| Unanswerable correctly declined | 8 | 8 | 0 | no measurable difference |
| Hallucinated on unanswerable | 0 | 0 | 0 | no measurable difference |
| False abstentions | 3 | 4 | +1 | no measurable difference |
| First-retrieval hit@5 (like-for-like retrieval) | 34 | 33 | -1 | no measurable difference |
| Context hit@5 (on contexts given to the generator) | 34 | 32 | -2 | no measurable difference |
| Web search used | 0 | 7 | +7 | measurable (+7) |

| RAGAS metric | Paired n | Wins | Losses | Verdict |
|---|---|---|---|---|
| RAGAS faithfulness (prose-level grounding signal) | 38 | 3 | 4 | no measurable difference |
| RAGAS response_relevancy | 38 | 1 | 0 | no measurable difference |
| RAGAS context_precision (on contexts given to the generator) | 41 | 2 | 0 | no measurable difference |
| RAGAS context_recall (on contexts given to the generator) | 41 | 0 | 1 | no measurable difference |

#### Self-RAG vs Corrective RAG

| Count metric | Corrective RAG | Self-RAG | Difference (questions) | Verdict |
|---|---|---|---|---|
| Correct answers | 37 | 36 | -1 | no measurable difference |
| Correct or partial | 38 | 38 | 0 | no measurable difference |
| Citation support | 37 | 37 | 0 | no measurable difference |
| Unanswerable correctly declined | 8 | 8 | 0 | no measurable difference |
| Hallucinated on unanswerable | 0 | 0 | 0 | no measurable difference |
| False abstentions | 3 | 4 | +1 | no measurable difference |
| First-retrieval hit@5 (like-for-like retrieval) | 34 | 33 | -1 | no measurable difference |
| Context hit@5 (on contexts given to the generator) | 33 | 32 | -1 | no measurable difference |
| Web search used | 8 | 7 | -1 | no measurable difference |

| RAGAS metric | Paired n | Wins | Losses | Verdict |
|---|---|---|---|---|
| RAGAS faithfulness (prose-level grounding signal) | 38 | 4 | 3 | no measurable difference |
| RAGAS response_relevancy | 38 | 1 | 0 | no measurable difference |
| RAGAS context_precision (on contexts given to the generator) | 41 | 1 | 0 | no measurable difference |
| RAGAS context_recall (on contexts given to the generator) | 41 | 0 | 0 | no measurable difference |

### Retrieval ablation

42 answerable questions, run `retrieval-20261025`.

| Mode | Hit@1 | Hit@5 | MRR | Evidence recall@5 |
|---|---|---|---|---|
| `dense` | 52.4% (22/42) | 83.3% (35/42) | 0.64 (n=42) | 0.75 (n=42) |
| `bm25` | 26.2% (11/42) | 59.5% (25/42) | 0.37 (n=42) | 0.54 (n=42) |
| `hybrid` | 52.4% (22/42) | 81.0% (34/42) | 0.63 (n=42) | 0.73 (n=42) |
| `hybrid_rerank` | 40.5% (17/42) | 83.3% (35/42) | 0.57 (n=42) | 0.74 (n=42) |

Candidate pool hit@20 (`retrieve_candidates`): 92.9% (39/42).

D6 reranker gate: hybrid_rerank hit@5 is 83.3% (35/42) against 81.0% (34/42) for hybrid, a gain of 1 question (the gate needs at least 3); hit@1 goes from 52.4% (22/42) to 40.5% (17/42). Result: FAIL (reranking stays disabled in production).

Provenance: 50 questions, eval set `eval-set-v1` (sha256 `316b1d683050e426ad5bf2324b9ca7211d30ea2566276320489e6acb538a470f`); corpus commit `a6e223d2f67558caa20589a03443e918b582943b`; judge gemini-3.5-flash-lite, prompt version 2, audit agreement on 11 items: correctness 10/11, citation support 11/11; RAGAS 0.4.4 with gemini-3.1-flash-lite.
````

## Failure labels

Rules in order: router_out_of_scope, structured_output_failure, retrieval_miss, grading_drop, false_abstention, hallucinated_unanswerable, web_used_failure, else needs_label.

| Label | baseline | corrective | self_rag |
|---|---|---|---|
| retrieval_miss (q008, q024, q025) | 3 | 3 | 3 |
| false_abstention (q029) | 1 | 1 | 1 |
| router_out_of_scope (q028) | 0 | 0 | 1 |
| needs_label | 0 | 1 | 1 |
| failed items | 4 | 5 | 6 |

15 rows, 13 labelled automatically, 2 needs_label with a proposal:
- corrective q034 (correctness 1): proposed unfaithful_generation. Judge: invents an `@update_state` decorator; RAGAS faithfulness 0.727 (low).
- self_rag q033 (correctness 1): proposed unfaithful_generation. Judge: invents a `stream.subgraphs` property on stream_events output; RAGAS faithfulness 1.000 does not flag it (prose-level signal; code blocks are not checked, D19).

No failed item in the committed runs is a hallucinated unanswerable, grading_drop, structured_output_failure or web_used_failure. Those rules are tested on hand-made data only.

## Decisions made

- The block uses `###` headings under a `## Results` heading that sits outside the markers.
- The paired RAGAS view uses the items scored in all three runs for every pair (as results/summary.md does), so baseline pairs equal summary.md and the self_rag vs corrective pair matches analysis_notes.md.
- Count verdict wording: "no measurable difference" (compare.NO_DIFFERENCE) or "measurable (+N)" (the analysis_notes.md wording). Count verdicts are neutral about direction because higher is not always better (false abstentions, web search).
- structured_output_failure reads only diagnostics (fallbacks, grading_failures, missing_grades, invalid_grades) and decision events carrying `fallback` or `grading_failed`. A retried attempt in failed_attempts is not treated as "on the path that produced the outcome". No failed committed item has either.
- grading_drop uses scores.context_hit@5 (contexts given to the generator). For the baseline the first retrieval is its contexts (D22), so a context miss there is a retrieval_miss.
- Proposals are keyword rules over the trace and the judge rationale: rewrite_query in trace, regenerate in trace, invent/hallucinat/unsupported, omit/missing/lacks, else judge_disagreement. stale_web_content is allowed but never proposed, because web_used_failure precedes it.
- Nothing here affects later modules, so DECISIONS.md is unchanged.

## Deviations from the prompt

- README.md did not exist, so the step "add a Results heading and markers at the end of the current README" created the file with only that heading, the markers and the block.
- Added `Settings.rerank_gate_min_gain` for the D6 threshold, because AGENTS.md forbids magic numbers; not in the prompt.
- I did not have the build-plan M15 spec in the repo to diff against, so the differences recorded are only those between this prompt and what the code and docs show: extra rows (false abstentions, web search used, p95 latency), pairwise comparisons including self_rag vs corrective, and the README created from scratch.

## Known issues and limitations

- `readme --check` takes the run names from results/summary.md and needs exactly one `retrieval-*` folder in results/runs.
- Citation support rows compare counts of judged items whose n differs (39/39/38); the README says so.
- Failure proposals are keyword heuristics; the human decides every label.

## Open questions for the human (session 1, answered in session 2)

- Read results/failure_review.md: 15 rows. The two proposed labels (corrective q034, self_rag q033) need a decision; the other 13 are automatic and pre-filled.

## Proposed follow-ups (out of scope)

- S2: README prose, Mermaid diagrams, CI badge, screenshots, release.

## Prerequisites for the next module

Bilal's answer on the 15 rows (format at the top of results/failure_review.md). S2 then applies the answers to the final_label column.

## S2 handoff

- Commands: `py tasks.py readme` (rewrite block), `py tasks.py readme --check`, `.venv\Scripts\python scripts\failure_breakdown.py` (rewrites the CSV and review file and so resets final_label; S2 must apply Bilal's answers after the last run of it).
- Files: results/failure_labels.csv, results/failure_review.md, README.md (block between the markers; everything outside it is S2's).
- Provenance values: see 1c. Production URL https://agentic-rag-docs-assistant.vercel.app. CI workflow "CI" (`.github/workflows/ci.yml`). Tags eval-set-v1 (commit c92688d), v1-baseline (commit a33490b), v2-agentic (commit 56a5043).
- Where each number lives: pipeline metrics in `summarize(run_dir)["overall"]` (fields in 1e) and results/runs/<run>/summary.json; paired and count verdicts in the README block and the results/summary.md "Paired" section; ablation in results/runs/retrieval-20261025/per_question.jsonl and table.md; web page numbers in web/public/results.json; mechanics (self-RAG path counts, q028, q049, regenerated items q006 q017 q032 q034) in results/analysis_notes.md; D6 gate in DECISIONS.md D6; judge audit in D9 and results/judge_audit.md; RAGAS validity caveat in D19.
- Example ids for 1f: out_of_scope q028 (self_rag); structured failure q049 (self_rag, corrective); used_web q043 (corrective), q025 (self_rag); first retrieval event q006; fallbacks: none committed.
- Screenshots in docs/screenshots/: langsmith-baseline-experiment.png, langsmith-baseline-trace.png, langsmith-baseline-vs-corrective.png, langsmith-corrective-trace.png, langsmith-eval-item.png, langsmith-self-rag-trace.png, langsmith-three-way-comparison.png, prod-baseline.png, ui-baseline.png, ui-corrective.png, ui-dark.png, ui-mobile.png, ui-s1-static.png, ui-self-rag.png.

## Session 2

### Prechecks
- git status clean; HEAD 2cee064 (S1); origin/main e8d8f52; status line changed from "Partial (session 1 of 2)" to "In progress (session 2 of 2)", now Done.
- LABEL DECISIONS were filled in (self_rag q033 judge_disagreement; all other rows OK).
- Claude in Chrome: the tools were loaded, but tabs_context_mcp returned "Browser extension is not connected". Not retried. Consequence: no demo GIF (README uses docs/screenshots/ui-self-rag.png), and the GitHub README render check is left to Bilal.

### Labels applied (results/failure_labels.csv; failure_breakdown.py not rerun)
- corrective q034: needs_label to final_label unfaithful_generation (the proposal, "all other rows OK"). self_rag q033: judge_disagreement. The other 13 rows kept their pre-filled labels. 15 rows, every final_label in the allowed list, no CR characters.

| final_label | baseline | corrective | self_rag |
|---|---|---|---|
| retrieval_miss | 3 | 3 | 3 |
| false_abstention | 1 | 1 | 1 |
| router_out_of_scope | 0 | 0 | 1 |
| unfaithful_generation | 0 | 1 | 0 |
| judge_disagreement | 0 | 0 | 1 |
| failed items | 4 | 5 | 6 |

### Files
- docs/failure-analysis.md (new), README.md (prose around the generated block), docs/cv-bullets.txt (new, 3 lines of 27, 32 and 31 words), results/failure_labels.csv (two final_label cells).

### Demo GIF and shot list
- No GIF (Chrome extension not connected). Budget check run first (gpt-oss-120b 12,000 tokens 6 requests, gpt-oss-20b 12,000 tokens 8 requests, gemini-embedding-001 500 tokens 4 requests: all fit); no asks were made. 0 production asks.
- 20-second shot list: (1) 1280 px wide viewport on the production URL, 2 s. (2) Click the "Version change" example, pipeline baseline, press Ask, show the trace rows and the answer with Sources, 7 s. (3) Select self_rag, press Ask on the same example, show the longer trace (decide_retrieval, retrieve, grade_documents, generate, verify_answer) and the answer, 9 s. (4) Hold 2 s on the answer so the trace difference is visible.

### Number trace
| # | Number or claim | Where used | Source and field |
|---|---|---|---|
| 1 | 50 questions, 42 answerable, 8 unanswerable | README Key findings, cv, failure-analysis | results/summary.md "Overall": items 50, answerable n 42; unanswerable = 50 - 42; per_question.jsonl category counts |
| 2 | Correct answers 38 / 37 / 36 of 42 (baseline / corrective / self_rag) | README, cv, failure-analysis | results/summary.md Overall row "correct (correctness = 2)": 38/42, 37/42, 36/42 |
| 3 | Differences -1, -1, -2 under the 3-question threshold = no measurable difference | README, failure-analysis | results/summary.md Overall (37-38, 36-38, 36-37); results/analysis_notes.md section 4 count table; threshold from Settings.compare_noise_margin = 3 and D19 |
| 4 | Baseline left 4 of 42 not correct: q008, q024, q025, q029 | README, failure-analysis | 42 - 38 = 4; results/failure_labels.csv rows pipeline=baseline (q008, q024, q025, q029) |
| 5 | Neither technique fixed any of those 4 | README, failure-analysis | results/runs/*/per_question.jsonl scores.correctness for q008, q024, q025, q029: baseline 0,1,0,0; corrective 0,0,0,0; self_rag 0,1,0,0 (none is 2); results/summary.md "Changed questions" |
| 6 | corrective broke q024 (1 to 0) and q034 (2 to 1) | README, failure-analysis | results/summary.md "Changed questions" corrective section |
| 7 | self_rag broke q028 (2 to 0) and q033 (2 to 1) | README, failure-analysis | results/summary.md "Changed questions" self_rag section |
| 8 | Mean tokens per question 2,334 / 4,577 / 6,847 (n=50) | README, cv, failure-analysis | results/summary.md Overall "mean tokens per question": 2333.560, 4577.300, 6847.080 |
| 9 | p95 latency 3.7 / 8.0 / 9.2 s | README, failure-analysis | results/summary.md Overall "p95 latency_ms": 3734, 8002, 9203 ms |
| 10 | Web search used 8 of 50 (corrective), 7 of 50 (self_rag), 0 of 50 (baseline); measurable (+8), (+7) | README, failure-analysis | results/summary.md Overall used_web; results/analysis_notes.md section 4 |
| 11 | RAGAS: no measurable difference for any pair, paired n 38 to 41; wins minus losses at most 2 in absolute value | README, failure-analysis | results/summary.md "Paired" sections: faithfulness n=38 (2/3, 3/4), response_relevancy n=38 (1/0, 1/0), context_precision n=41 (2/1, 2/0), context_recall n=41 (0/1, 0/1); S vs C from analysis_notes.md section 4 (4/3, 1/0, 1/0, 0/0) |
| 12 | D6 gate: hybrid hit@5 34/42, hybrid_rerank 35/42, gain 1, threshold 3; hit@1 22 to 17 of 42 | README, failure-analysis | results/runs/retrieval-20261025/table.md; docs/DECISIONS.md D6 gate decision |
| 13 | Counts per label per pipeline (retrieval_miss 3/3/3 = 9; false_abstention 1/1/1 = 3; router_out_of_scope 0/0/1; unfaithful_generation 0/1/0; judge_disagreement 0/0/1; failed items 4/5/6; 15 rows) | failure-analysis | results/failure_labels.csv, column final_label grouped by pipeline (15 rows) |
| 14 | q028: baseline 2, corrective 2, self_rag 0; no retrieval event; self_rag first-retrieval hit@5 33/42 vs corrective 34/42 | failure-analysis | per_question.jsonl scores.correctness; results/analysis_notes.md section 3; summary.md Overall first-retrieval hit@5 |
| 15 | q034: corrective 1, self_rag 2, baseline 2; self_rag regenerated once; RAGAS faithfulness corrective 0.727 | failure-analysis | per_question.jsonl q034 all three runs; results/failure_labels.csv ragas_faithfulness; analysis_notes.md section 1 and 3 |
| 16 | q033 self_rag judge correctness 1, citation_support 0; RAGAS faithfulness 1.000 | failure-analysis, README | results/failure_labels.csv self_rag q033 (ragas_faithfulness, note); runs/self_rag-20261121-0744/judge_v2.jsonl |
| 17 | q024: baseline 1, corrective 0, self_rag 1; corrective kept 1 of 5 chunks, self_rag kept 2 of 5 | failure-analysis | per_question.jsonl scores; results/failure_review.md q024 trace lines |
| 18 | Regeneration ran on 4 of 50 items (q006, q017, q032, q034); only q034 changed its outcome | failure-analysis | results/analysis_notes.md section 3 table and section 1 |
| 19 | Hand audit 11 items, correctness agreement 10/11, citation support 11/11; baseline run only | README, failure-analysis | docs/DECISIONS.md D9 audit result; results/judge_audit.md |
| 20 | RAGAS sanity check 0.896 (8 items) vs 0.963 (3 items) | README | docs/progress/M09-ragas-experiments.md; docs/DECISIONS.md D19 update |
| 21 | Eval set 28 single, 8 multi, 6 version, 8 unanswerable; 11 of 42 real-sourced | README | data/eval/README.md composition table; D14 |
| 22 | Cap: 5 questions per hour per IP, 32 per day | README | src/ragdocs/config.py rate_limit_per_ip_per_hour = 5, daily_global_cap = 32 |
| 23 | Corpus: commit a6e223d2f67558caa20589a03443e918b582943b, 41 pages, 553 chunks | README | data/index/manifest.json |
| 24 | Token ratios "about 2 and 3 times" | cv | 4577.300 / 2333.560 = 1.96; 6847.080 / 2333.560 = 2.93 (computed from the summary.md values) |
| 25 | cv-bullets word counts 27, 32, 31 (each under 35) | cv | awk field count on docs/cv-bullets.txt |


### Independent check (separate general-purpose agent)
Given: the three files, the table above, the noise rules and the source paths. Report, summarised:
- Task 1: one mismatch. failure-analysis.md (judge_disagreement) offered a second reading, that the answer used only graph.stream(subgraphs=True); the stored full answer also contains a stream_events(version="v3") snippet reading stream.subgraphs, as the reference does. The 600-character excerpt in failure_review.md hid it. Fixed: paragraph rewritten.
- Wording issues, all fixed: README "three multi-hop questions need evidence from several chunks" now says q031, q032 and q036 have gold sections that resolve to 6, 4 and 4 chunks (M03 line 241); q029 "failure is in generation over multi-chunk evidence" replaced by "the files do not show why the generator abstained"; q024 sentence now gives both judge rationales; "the two measurable differences" reworded (cost has no verdict); README CI list says "audit of the frontend runtime dependencies"; README key findings flags q033 as a judge disagreement.
- Stale file noted: results/failure_review.md still shows q033 as unfaithful_generation (proposed) because it is the generated file from before the decisions; not regenerated (it would reset final_label). failure-analysis.md says so.
- Tasks 2 to 5 (noise verdicts, better/worse claims, adjectives, cv-bullets rules): no mismatches. The v1.0 tag listed in the README does not exist yet (created at the end of the session).

### Verification
- Before this file was written: py tasks.py lint -> 187 files already formatted, ruff checks pass; py tasks.py test -> 525 passed, 1 deselected in 30.34s; py tasks.py readme --check -> README results block is up to date.
- CI results, the production smoke, the secret scan and the v1.0 tag happen after this file is committed and are reported in the final message of the session, not here.

### Differences from the build-plan spec
- The build-plan M15 spec was not available (S1 recorded this); the session prompt was the contract. No other differences known.

### Decisions made
- Failure labels follow Bilal's answers; the LangSmith links in failure-analysis.md are run ids because no trace URL is committed for the failed items.