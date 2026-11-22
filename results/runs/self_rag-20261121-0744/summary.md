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
