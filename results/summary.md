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
