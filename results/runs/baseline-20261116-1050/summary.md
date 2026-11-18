# Run summary: baseline-20261116-1050

Pipeline: baseline. Tracing enabled: True.
Judge: gemini-3.5-flash-lite, prompt version 2 (source judge_v2.jsonl), judged 39/39 eligible items.

Rates are shown as rate (count/n). Correctness uses n = every answerable item;
a false abstention counts as correctness 0.

## Overall

| Field | Value |
|---|---|
| items | 50 |
| answerable n | 42 |
| correct (correctness = 2) | 0.905 (38/42) |
| correct or partial (correctness >= 1) | 0.929 (39/42) |
| mean correctness (0-2) | 1.833 (n=42) |
| citation_support (judged items) | 1.000 (39/39) |
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

## Per category

| Field | single | multi | version | unanswerable |
|---|---|---|---|---|
| items | 28 | 8 | 6 | 8 |
| answerable n | 28 | 8 | 6 | 0 |
| correct (correctness = 2) | 0.893 (25/28) | 0.875 (7/8) | 1.000 (6/6) | - |
| correct or partial (correctness >= 1) | 0.929 (26/28) | 0.875 (7/8) | 1.000 (6/6) | - |
| mean correctness (0-2) | 1.821 (n=28) | 1.750 (n=8) | 2.000 (n=6) | - |
| citation_support (judged items) | 1.000 (26/26) | 1.000 (7/7) | 1.000 (6/6) | - |
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

## Totals (generation)

- Tokens in: 95674; tokens out: 21004; LLM calls: 50; calls without usage data: 0
- openai/gpt-oss-120b: 95674 in, 21004 out, 50 calls
- Judge: 86114 in, 2430 out, 39 calls, 0 cached verdicts
