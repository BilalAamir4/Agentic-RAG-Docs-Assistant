# Analysis notes: baseline, corrective and self-RAG (M11)

Facts only, taken from committed files: results/runs/baseline-20261116-1050, results/runs/corrective-20261120-1852, results/runs/self_rag-20261121-0744 (per_question.jsonl, judge_v2.jsonl, ragas_scores.jsonl, failed_attempts.jsonl), results/summary.md and docs/progress/M11-self-rag.md. Correctness is the judge_v2 verdict (0 to 2); an abstained answerable item counts as 0. Abbreviations: B baseline, C corrective, S self_rag.

## 1. Questions whose outcome differs between pipelines

Outcome per pipeline is written B / C / S. "Correctness" is judge correctness. A RAGAS difference is a paired difference over 0.2 on at least one pair of runs. "Contexts" is the number of chunks passed to the generator (B always 5).

### single

- q024: correctness 1 / 0 / 1. C graded 1 context relevant and generated from it (judge: attributes the failure to ordering, misses reducers). S passed 2 contexts, verify passed the answer first time (no regenerate), judge: misses reducers but claims supported. RAGAS faithfulness B 0.89, C 0.29, S 0.86; context_precision B 0.33, C 0.0, S 0.5.
- q028: correctness 2 / 2 / 0. S: decide_retrieval returned needs_docs False, "Question about Pregel, not LangGraph.", then out_of_scope (no retrieval event, abstained). RAGAS context_precision B 0.25, C 1.0 (S has no contexts).
- q001: correctness 2 / 2 / 2. RAGAS faithfulness B 0.60, C 1.0, S 0.89. Same node path for C and S (no regenerate); B 5 contexts, C and S 4.
- q002: correctness 2 / 2 / 2. RAGAS response_relevancy C 0.71, S 0.92. Same path, 5 contexts each; no deciding trace step.
- q006: correctness 2 / 2 / 2. RAGAS context_precision B 0.5, C 1.0, S 1.0. S verify flagged an unsupported claim, regenerate, verify ok. B 5 contexts, C and S 2.
- q014: correctness 2 / 2 / 2. RAGAS faithfulness B 1.0, C 1.0, S 0.5; context_precision B 0.42, C 1.0, S 1.0. S verify ok first time (no regenerate); 2 contexts for C and S, 5 for B.
- q017: correctness 2 / 2 / 2. RAGAS faithfulness C 0.71, S 1.0. S verify flagged an unsupported claim, regenerate, verify ok.
- q018: correctness 2 / 2 / 2. RAGAS faithfulness B 0.57, C 1.0, S 1.0. No regenerate; 4 contexts for C and S, 5 for B.
- q027: correctness 2 / 2 / 2. RAGAS response_relevancy B 0.63, C 0.92, S 0.85. No regenerate; 4 contexts for C and S.

### multi

- q033: correctness 2 / 2 / 1. S verify passed the answer first time (no regenerate); judge: invents a `stream.subgraphs` property on `stream_events` output. No RAGAS difference over 0.2.
- q034: correctness 2 / 1 / 2. C judge: invents an `@update_state` decorator. S verify flagged an unsupported claim, regenerate, verify ok, then correct. RAGAS faithfulness B 0.71, C 0.73, S 1.0.
- q031: correctness 2 / 2 / 2. RAGAS context_recall B 1.0, C 0.0, S 0.0. C passed 2 contexts, S 3, B 5.
- q032: correctness 2 / 2 / 2. RAGAS faithfulness B 1.0, C 0.67, S 1.0. S verify flagged an unsupported claim, regenerate, verify ok (5 contexts).
- q036: correctness 2 / 2 / 2. RAGAS faithfulness B 0.91, C 0.54, S 0.69. Same node path for C and S (no regenerate), 5 contexts each.

### version

- q009: correctness 2 / 2 / 2. RAGAS faithfulness B 1.0, C 1.0, S 0.75. No regenerate; 4 contexts for C and S.
- q040: correctness 2 / 2 / 2. RAGAS faithfulness B 1.0, C 0.89, S 0.67. No regenerate; 5 contexts each.

### unanswerable

- No question differs. All 8 are abstained (abstention_correct 8/8, hallucinated 0/8) in B, C and S.

## 2. Pre-registered expectations versus results

Order follows the request: 1 the 7 grader-accepted retrieval misses, 2 the 8 rewrite items, 3 q024 and q034, 4 the cost forecast, 5 q028.

1. Seven grader-accepted retrieval misses (q008, q012, q018, q024, q031, q038, q039). Expected: none becomes correct (2) through better retrieval; the five already correct stay correct or regress; q008 and q024 do not become correct. Happened: q012, q018, q031, q038, q039 stay 2; q008 stays a false abstention (0); q024 is 1 (not 2). All 7 took the path retrieve, grade_documents, generate, verify_answer. Held.
2. Eight rewrite items (q025, q043 to q050). Expected (carried from corrective): second grading 0 of 5 relevant on all 8, same outcomes as corrective. Happened: outcomes are the same on 8 of 8 (q025 false abstention, q043 to q050 abstained, verify skipped on every abstained answer). Second grading was 0 of 5 on 7 of 8; q047 graded 1 of 5 relevant, so it skipped web search and generated (abstained). used_web is 7 of 8. Held for outcomes; did not hold for "0 of 8" (q047).
3. q024 and q034. Expected: items where verify and regenerate could change the outcome. Happened: q034 verify flagged an unsupported claim, regenerated, and ended correct (2; corrective 1). q024 went from 0 (C) to 1 (S) with no verify or regenerate action (verify passed first time; S passed 2 contexts against 1 in C). Held for q034; did not hold for q024 as a verify effect.
4. Cost forecast. Expected (revised in S2): gpt-oss-20b 261,000 to 363,000 tokens per 50 items (S1: 368,950 to 484,000), 2 to 3 calendar days. Happened: gpt-oss-20b 243,679 tokens (185,625 in, 58,054 out) over 157 calls; gpt-oss-120b 98,675 tokens over 53 calls; the run spanned 2026-11-21 and 2026-11-22 (2 calendar days, paused at the daily cap after 22 items). Tokens: did not hold (below both forecast ranges). Calendar days: held.
5. q028. Expected: routed out of scope, a false abstention and a first-retrieval hit@5 miss. Happened: decide_retrieval returned needs_docs False with reason "Question about Pregel, not LangGraph.", then out_of_scope; abstained, no retrieval event. Held.

## 3. Self-RAG mechanics

Item counts by path (50 items):

| Path | Items |
|---|---|
| out_of_scope (q028) | 1 |
| verify ok first time | 34 |
| regenerated, then verify ok (q006, q017, q032, q034) | 4 |
| regenerated, then abstained | 0 |
| abstained by verify (abstain node) | 0 |
| verify skipped because the generator abstained | 11 (q008, q025, q029, q043 to q050) |
| fallback: decide_failed | 0 |
| fallback: verify_failed | 0 |
| fallback: regenerate_failed | 0 |

- Total: 1 + 34 + 4 + 11 = 50. verify_answer ran 53 times (49 first runs plus 4 re-verifications).
- Failed structured calls (D26 amendment): structured_output_failures 2 plus structured-call fallbacks 0 = 2 in total.
- rate_limited_attempts: 0 in S (B 10, C 0).
- False abstentions: 4 of 42 answerable. 1 from the router: q028. 3 from generate after retrieval (verify skipped): q008, q025, q029. B and C had the same 3 (q008, q025, q029).
- First-retrieval hit@5: S 33/42, C 34/42, B 34/42. The whole 1-item gap between S and C comes from q028 having no retrieval event. The other 41 answerable items have the same first-retrieval hit across all three runs.
- q049 (unanswerable, abstained in all three runs): structured-output failures on the same item and the same gpt-oss-20b grader in both agentic runs, at different nodes. C: Groq 400 json_validate_failed on rewrite_query's RewrittenQuery call (results/error_reclassifications.json evidence). S: BadRequestError twice at grade_documents (failed_attempts.jsonl, 2026-11-22T09:36:07Z and 09:37:12Z); the error body was not stored. A replay of the same grade_documents request in a throwaway probe succeeded, and the third attempt (resume) completed. The failure is intermittent and the item repeats it across runs; it is not a one-off.

## 4. Noise verdicts

Rules (D19): a count metric differing by fewer than 3 questions is "no measurable difference". A RAGAS metric: per paired item a win or loss is a difference over 0.2; wins minus losses must be at least 3. S against C is computed with the harness paired_section over the three-run common items (the committed summary.md pairs each run against baseline only).

### Count metrics (differences in questions)

| Metric (B / C / S) | C vs B | S vs B | S vs C |
|---|---|---|---|
| correct, correctness = 2 (38 / 37 / 36) | none | none | none |
| correct or partial (39 / 38 / 38) | none | none | none |
| first-retrieval hit@5 (34 / 34 / 33) | none | none | none |
| context_hit@5 (34 / 33 / 32) | none | none | none |
| false_abstention (3 / 3 / 4) | none | none | none |
| abstention_correct (8 / 8 / 8) | none | none | none |
| hallucinated (0 / 0 / 0) | none | none | none |
| citation_support, items supported (39 / 37 / 37; judged 39 / 39 / 38) | none | none | none |
| used_web (0 / 8 / 7) | measurable (+8) | measurable (+7) | none |
| items with at least one structured_output failure (0 / 1 / 1) | none | none | none |

Cost rows (mean llm_calls 1.0 / 2.32 / 4.2, mean tokens per question 2,334 / 4,577 / 6,847, p95 latency 3,734 / 8,002 / 9,203 ms) are measured values, not question counts, and are not given a noise verdict.

### Paired correctness and RAGAS (better / worse items)

| Metric | C vs B | S vs B | S vs C |
|---|---|---|---|
| correctness | 0 / 2, none | 0 / 2, none | 2 / 2, none |
| RAGAS faithfulness | 2 / 3, none | 3 / 4, none | 4 / 3, none |
| RAGAS response_relevancy | 1 / 0, none | 1 / 0, none | 1 / 0, none |
| RAGAS context_precision | 2 / 1, none | 2 / 0, none | 1 / 0, none |
| RAGAS context_recall | 0 / 1, none | 0 / 1, none | 0 / 0, none |

Verdict: no measurable difference on correctness or any RAGAS metric for any pair. The only measurable differences are in used_web and in cost (more LLM calls, tokens and latency per question for the agentic pipelines).
