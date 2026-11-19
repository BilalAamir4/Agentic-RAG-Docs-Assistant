# Run comparison

Judge gemini-3.5-flash-lite, prompt version 2. Rates are rate (count/n); correctness n = every answerable item.

## Overall

| Field | baseline-20261116-1050 |
|---|---|
| items | 50 |
| answerable n | 42 |
| correct (correctness = 2) | 0.905 (38/42) |
| correct or partial (correctness >= 1) | 0.929 (39/42) |
| mean correctness (0-2) | 1.833 (n=42) |
| citation_support (judged items) | 1.000 (39/39) |
| context_hit@5 (on contexts given to the generator) | 0.810 (34/42) |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.726 (n=42) |
| mean must_mention coverage (soft signal, D15) | 0.905 (n=42) |
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
| RAGAS faithfulness (prose-level grounding signal) | 0.922 (39) |
| RAGAS response_relevancy | 0.813 (39) |
| RAGAS context_precision (on contexts given to the generator) | 0.720 (42) |
| RAGAS context_recall (on contexts given to the generator) | 0.845 (42) |

## single

| Field | baseline-20261116-1050 |
|---|---|
| items | 28 |
| answerable n | 28 |
| correct (correctness = 2) | 0.893 (25/28) |
| correct or partial (correctness >= 1) | 0.929 (26/28) |
| mean correctness (0-2) | 1.821 (n=28) |
| citation_support (judged items) | 1.000 (26/26) |
| context_hit@5 (on contexts given to the generator) | 0.786 (22/28) |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.786 (n=28) |
| mean must_mention coverage (soft signal, D15) | 0.893 (n=28) |
| false_abstention | 0.071 (2/28) |
| abstention_correct (unanswerable) | - |
| hallucinated (unanswerable) | - |
| mean llm_calls | 1.000 (n=28) |
| p50 latency_ms | 2062 ms |
| p95 latency_ms | 3447 ms |
| mean tokens per question | 2399.107 (n=28) |
| used_web | 0.000 (0/28) |
| structured_output_failures (failed attempts before success) | 0 (n=28) |
| items with >= 1 structured_output failure | 0.000 (0/28) |
| rate-limited attempts (not counted above) | 10 (n=28) |
| RAGAS faithfulness (prose-level grounding signal) | 0.908 (26) |
| RAGAS response_relevancy | 0.818 (26) |
| RAGAS context_precision (on contexts given to the generator) | 0.772 (28) |
| RAGAS context_recall (on contexts given to the generator) | 0.857 (28) |

## multi

| Field | baseline-20261116-1050 |
|---|---|
| items | 8 |
| answerable n | 8 |
| correct (correctness = 2) | 0.875 (7/8) |
| correct or partial (correctness >= 1) | 0.875 (7/8) |
| mean correctness (0-2) | 1.750 (n=8) |
| citation_support (judged items) | 1.000 (7/7) |
| context_hit@5 (on contexts given to the generator) | 0.875 (7/8) |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.500 (n=8) |
| mean must_mention coverage (soft signal, D15) | 0.875 (n=8) |
| false_abstention | 0.125 (1/8) |
| abstention_correct (unanswerable) | - |
| hallucinated (unanswerable) | - |
| mean llm_calls | 1.000 (n=8) |
| p50 latency_ms | 2772 ms |
| p95 latency_ms | 3610 ms |
| mean tokens per question | 2368.500 (n=8) |
| used_web | 0.000 (0/8) |
| structured_output_failures (failed attempts before success) | 0 (n=8) |
| items with >= 1 structured_output failure | 0.000 (0/8) |
| rate-limited attempts (not counted above) | 0 (n=8) |
| RAGAS faithfulness (prose-level grounding signal) | 0.907 (7) |
| RAGAS response_relevancy | 0.817 (7) |
| RAGAS context_precision (on contexts given to the generator) | 0.479 (8) |
| RAGAS context_recall (on contexts given to the generator) | 0.688 (8) |

## version

| Field | baseline-20261116-1050 |
|---|---|
| items | 6 |
| answerable n | 6 |
| correct (correctness = 2) | 1.000 (6/6) |
| correct or partial (correctness >= 1) | 1.000 (6/6) |
| mean correctness (0-2) | 2.000 (n=6) |
| citation_support (judged items) | 1.000 (6/6) |
| context_hit@5 (on contexts given to the generator) | 0.833 (5/6) |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.750 (n=6) |
| mean must_mention coverage (soft signal, D15) | 1.000 (n=6) |
| false_abstention | 0.000 (0/6) |
| abstention_correct (unanswerable) | - |
| hallucinated (unanswerable) | - |
| mean llm_calls | 1.000 (n=6) |
| p50 latency_ms | 2430 ms |
| p95 latency_ms | 3420 ms |
| mean tokens per question | 2352.833 (n=6) |
| used_web | 0.000 (0/6) |
| structured_output_failures (failed attempts before success) | 0 (n=6) |
| items with >= 1 structured_output failure | 0.000 (0/6) |
| rate-limited attempts (not counted above) | 0 (n=6) |
| RAGAS faithfulness (prose-level grounding signal) | 1.000 (6) |
| RAGAS response_relevancy | 0.784 (6) |
| RAGAS context_precision (on contexts given to the generator) | 0.798 (6) |
| RAGAS context_recall (on contexts given to the generator) | 1.000 (6) |

## unanswerable

| Field | baseline-20261116-1050 |
|---|---|
| items | 8 |
| answerable n | 0 |
| correct (correctness = 2) | - |
| correct or partial (correctness >= 1) | - |
| mean correctness (0-2) | - |
| citation_support (judged items) | - |
| context_hit@5 (on contexts given to the generator) | - |
| mean context_evidence_recall@5 (on contexts given to the generator) | - |
| mean must_mention coverage (soft signal, D15) | - |
| false_abstention | - |
| abstention_correct (unanswerable) | 1.000 (8/8) |
| hallucinated (unanswerable) | 0.000 (0/8) |
| mean llm_calls | 1.000 (n=8) |
| p50 latency_ms | 1822 ms |
| p95 latency_ms | 4181 ms |
| mean tokens per question | 2054.750 (n=8) |
| used_web | 0.000 (0/8) |
| structured_output_failures (failed attempts before success) | 0 (n=8) |
| items with >= 1 structured_output failure | 0.000 (0/8) |
| rate-limited attempts (not counted above) | 0 (n=8) |
| RAGAS faithfulness (prose-level grounding signal) | - |
| RAGAS response_relevancy | - |
| RAGAS context_precision (on contexts given to the generator) | - |
| RAGAS context_recall (on contexts given to the generator) | - |

## Changed questions (against baseline-20261116-1050)

- only one run given

## Paired

Means over items scored in every compared run (n). A paired item is better or worse when the difference exceeds 0.2; the verdict is "no measurable difference" unless wins minus losses is 3 or more (D19).

- only one run given
