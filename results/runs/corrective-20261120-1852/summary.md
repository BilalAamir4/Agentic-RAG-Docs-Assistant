# Run summary: corrective-20261120-1852

Pipeline: corrective. Tracing enabled: True.
Judge: gemini-3.5-flash-lite, prompt version 2 (source judge_v2.jsonl), judged 39/39 eligible items.

Rates are shown as rate (count/n). Correctness uses n = every answerable item;
a false abstention counts as correctness 0.

## Overall

| Field | Value |
|---|---|
| items | 50 |
| answerable n | 42 |
| correct (correctness = 2) | 0.881 (37/42) |
| correct or partial (correctness >= 1) | 0.905 (38/42) |
| mean correctness (0-2) | 1.786 (n=42) |
| citation_support (judged items) | 0.949 (37/39) |
| first-retrieval hit@5 (like-for-like retrieval) | 0.810 (34/42) |
| context_hit@5 (on contexts given to the generator) | 0.786 (33/42) |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.702 (n=42) |
| mean must_mention coverage (soft signal, D15) | 0.905 (n=42) |
| false_abstention | 0.071 (3/42) |
| abstention_correct (unanswerable) | 1.000 (8/8) |
| hallucinated (unanswerable) | 0.000 (0/8) |
| mean llm_calls | 2.320 (n=50) |
| p50 latency_ms | 3167 ms |
| p95 latency_ms | 8002 ms |
| mean tokens per question | 4577.300 (n=50) |
| used_web | 0.160 (8/50) |
| structured_output_failures (failed attempts before success) | 2 (n=50) |
| items with >= 1 structured_output failure | 0.040 (2/50) |
| rate-limited attempts (not counted above) | 0 (n=50) |

## Per category

| Field | single | multi | version | unanswerable |
|---|---|---|---|---|
| items | 28 | 8 | 6 | 8 |
| answerable n | 28 | 8 | 6 | 0 |
| correct (correctness = 2) | 0.893 (25/28) | 0.750 (6/8) | 1.000 (6/6) | - |
| correct or partial (correctness >= 1) | 0.893 (25/28) | 0.875 (7/8) | 1.000 (6/6) | - |
| mean correctness (0-2) | 1.786 (n=28) | 1.625 (n=8) | 2.000 (n=6) | - |
| citation_support (judged items) | 0.962 (25/26) | 0.857 (6/7) | 1.000 (6/6) | - |
| first-retrieval hit@5 (like-for-like retrieval) | 0.786 (22/28) | 0.875 (7/8) | 0.833 (5/6) | - |
| context_hit@5 (on contexts given to the generator) | 0.750 (21/28) | 0.875 (7/8) | 0.833 (5/6) | - |
| mean context_evidence_recall@5 (on contexts given to the generator) | 0.750 (n=28) | 0.500 (n=8) | 0.750 (n=6) | - |
| mean must_mention coverage (soft signal, D15) | 0.893 (n=28) | 0.875 (n=8) | 1.000 (n=6) | - |
| false_abstention | 0.071 (2/28) | 0.125 (1/8) | 0.000 (0/6) | - |
| abstention_correct (unanswerable) | - | - | - | 1.000 (8/8) |
| hallucinated (unanswerable) | - | - | - | 0.000 (0/8) |
| mean llm_calls | 2.071 (n=28) | 2.000 (n=8) | 2.000 (n=6) | 3.750 (n=8) |
| p50 latency_ms | 2942 ms | 3692 ms | 3047 ms | 6638 ms |
| p95 latency_ms | 6515 ms | 4243 ms | 3816 ms | 8706 ms |
| mean tokens per question | 4311.429 (n=28) | 4351.125 (n=8) | 4441.333 (n=6) | 5836.000 (n=8) |
| used_web | 0.036 (1/28) | 0.000 (0/8) | 0.000 (0/6) | 0.875 (7/8) |
| structured_output_failures (failed attempts before success) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 2 (n=8) |
| items with >= 1 structured_output failure | 0.000 (0/28) | 0.000 (0/8) | 0.000 (0/6) | 0.250 (2/8) |
| rate-limited attempts (not counted above) | 0 (n=28) | 0 (n=8) | 0 (n=6) | 0 (n=8) |

## Totals (generation)

- Tokens in: 178264; tokens out: 50601; LLM calls: 116; calls without usage data: 0
- openai/gpt-oss-120b: 70779 in, 19214 out, 50 calls
- openai/gpt-oss-20b: 107485 in, 31387 out, 66 calls
- Judge: 66166 in, 2540 out, 39 calls, 0 cached verdicts
