# Run summary: baseline-20261116-0919

Pipeline: baseline. Tracing enabled: True.
Judge: gemini-3.5-flash-lite, prompt version 1 (source judge_v1.jsonl), judged 41/41 eligible items.

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

## Per category

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

## Totals (generation)

- Tokens in: 91874; tokens out: 18524; LLM calls: 50; calls without usage data: 0
- openai/gpt-oss-120b: 91874 in, 18524 out, 50 calls
- Judge: 94959 in, 2629 out, 41 calls, 0 cached verdicts
