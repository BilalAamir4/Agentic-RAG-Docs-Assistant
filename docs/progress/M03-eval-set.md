M03: Eval set
Status: Done
Date: 2026-10-22

Goal
Curate, harden, and verify a frozen 50-item evaluation benchmark (data/eval/eval_set.jsonl) across four balanced categories (28 single, 8 multi, 6 version, 8 unanswerable) anchored to stable documentation sections without heading leakage, backed by 11 verbatim-verified real user sources, rigorous unanswerable keyword absence verification, mechanical grounding audits, and 100% human verification sign-off.

What was built
- data/eval/eval_set.jsonl: Curated 50-item evaluation dataset (28 single, 8 multi, 6 version, 8 unanswerable) with 50/50 items verified and 11 real user sources.
- data/eval/README.md: Comprehensive evaluation dataset documentation covering composition, schemas, absence rules, scoring semantics, and review procedures.
- data/eval/REVIEW.md: Generated human review sheet formatting all 50 items with evidence chunks and unanswerable absence search notes.
- data/eval/absence_terms.json: Keyword search term definitions for all 8 unanswerable items (q043-q050).
- data/eval/absence_adjudication.json: Formal adjudication entries clearing irrelevant corpus matches for q043, q046, and q050.
- data/eval/source_quotes.json: Machine-checkable registry storing URLs, authors, post positions, and verbatim OP problem quotes for all 11 real user sources.
- data/eval/source_snapshots/: Local UTF-8 thread snapshots (gitignored) storing thread titles, authors, and post text for verbatim verification.
- data/eval/SOURCES_LOG.md: Sourcing audit log tracking verified verbatim quotes, corrections, reverted sources, and release proof URLs.
- data/eval/SOURCE_SPOTCHECK.md: Spotcheck audit table and verdict classifications comparing active source threads against item questions.
- data/eval/AUDIT.md: Mechanical audit report detailing evidence resolution, evidence-only identifier presence, grounding, and noise metrics.
- data/eval/STATUS_AUDIT.md: Historical audit log of baseline validator metrics and checklist progress.
- src/ragdocs/eval/config.py: Configuration constants defining MIN_REAL_SOURCES = 11.
- src/ragdocs/eval/validate.py: Validation engine executing 11 checks (parsing, IDs, category counts, evidence resolution, 4-gram overlap, page spread, real user sourcing, must-mention presence, verification status, unanswerable absence, source quotes).
- src/ragdocs/eval/review.py: Human review markdown generator formatting items, evidence chunks, and keyword absence searches.
- src/ragdocs/eval/absence.py: Keyword absence search engine with word-boundary regex (`(?<![A-Za-z0-9_])term(?![A-Za-z0-9_])`), context extraction, and adjudication clearance checking.
- src/ragdocs/eval/audit.py: Mechanical audit scanner evaluating evidence resolution, identifier presence, reference-answer code token grounding, noise reporting, and version proof URLs.
- src/ragdocs/eval/verify_sources.py: Verbatim source quote verifier checking normalized contiguous substring matches, author presence, non-title OP text, and minimum length.
- scripts/validate_eval.py: CLI wrapper running full dataset validation over data/eval/eval_set.jsonl.
- scripts/make_review_sheet.py: CLI script generating data/eval/REVIEW.md from eval_set.jsonl and chunks.jsonl.
- scripts/check_unanswerable.py: CLI script verifying keyword absence and clearance for unanswerable items across chunks.jsonl.
- scripts/audit_eval.py: CLI script running mechanical evaluation audits and writing data/eval/AUDIT.md.
- scripts/verify_source_quotes.py: CLI script verifying external user source quotes against local thread snapshots.
- tasks.py: Task runner commands added for validate-eval, verify-sources, check-unanswerable, and audit-eval.
- tests/test_validate_eval.py: Pytest suite testing all validator checks, absence checking, and requirement flags.
- tests/test_verify_source_quotes.py: Pytest suite testing verbatim quote verification, author checking, normalization, and registration rules.
- .gitignore: Added entry ignoring local snapshot files (data/eval/source_snapshots/).

How to run
- Run dataset validator: `py tasks.py validate-eval`
- Run validator requiring all 50 verified: `py tasks.py validate-eval --require-verified`
- Run source quote verifier: `py tasks.py verify-sources`
- Run unanswerable absence check: `py tasks.py check-unanswerable`
- Run mechanical audit: `py tasks.py audit-eval`
- Regenerate review sheet: `.venv\Scripts\python scripts/make_review_sheet.py`
- Run test suite: `py tasks.py test`
- Run linter and formatter: `py tasks.py lint`

Verification
Commands executed on Windows 11 PowerShell:

1. Dataset validation (`py tasks.py validate-eval`):
```text
=== Evaluation Dataset Validation Report ===
[PASS] Parse as EvalItem: Successfully parsed 50 items
[PASS] IDs unique and sequential: IDs are unique and exactly q001..q050
[PASS] Category composition: Category counts exact: single=28/28, multi=8/8, version=6/6, unanswerable=8/8
[PASS] Evidence resolution: All evidence references resolve to existing chunks
[PASS] No 4-word overlap: No 4-word overlap found between questions and evidence chunks
[PASS] Page spread: Page spread rules satisfied (27 pages used; max items per page: 5)
[PASS] Real user question sourcing: 11/42 answerable items adapted from real user sources
[PASS] Must-mention identifiers: All must_mention identifiers verified verbatim in evidence chunks
[PASS] Verification status: 50/50 items marked verified
[PASS] Unanswerable absence: All unanswerable items have zero uncleared keyword hits
[PASS] Source quotes verified: All 11 external source(s) have registered quotes and snapshots
============================================
Overall Result: PASSED
```

2. Validator enforcement check (`py tasks.py validate-eval --require-verified`):
```text
=== Evaluation Dataset Validation Report ===
[PASS] Parse as EvalItem: Successfully parsed 50 items
[PASS] IDs unique and sequential: IDs are unique and exactly q001..q050
[PASS] Category composition: Category counts exact: single=28/28, multi=8/8, version=6/6, unanswerable=8/8
[PASS] Evidence resolution: All evidence references resolve to existing chunks
[PASS] No 4-word overlap: No 4-word overlap found between questions and evidence chunks
[PASS] Page spread: Page spread rules satisfied (27 pages used; max items per page: 5)
[PASS] Real user question sourcing: 11/42 answerable items adapted from real user sources
[PASS] Must-mention identifiers: All must_mention identifiers verified verbatim in evidence chunks
[PASS] Verification status: 50/50 items marked verified
[PASS] Unanswerable absence: All unanswerable items have zero uncleared keyword hits
[PASS] Source quotes verified: All 11 external source(s) have registered quotes and snapshots
============================================
Overall Result: PASSED
```

3. Source quote verification (`py tasks.py verify-sources`):
```text
=== Source Quote Verification Report ===
Found 11 item(s) with external user sources.
[PASS] q001: source quote verified verbatim
[PASS] q007: source quote verified verbatim
[PASS] q011: source quote verified verbatim
[PASS] q016: source quote verified verbatim
[PASS] q018: source quote verified verbatim
[PASS] q024: source quote verified verbatim
[PASS] q026: source quote verified verbatim
[PASS] q030: source quote verified verbatim
[PASS] q031: source quote verified verbatim
[PASS] q032: source quote verified verbatim
[PASS] q033: source quote verified verbatim
========================================
Overall Result: PASSED (all source quotes match snapshots verbatim)
```

4. Unanswerable keyword absence check (`py tasks.py check-unanswerable`):
```text
=== Unanswerable Absence Verification Report ===

Item: q043 - Which RetryPolicy argument caps the total wall-clock time a node may spend across all of its retry attempts?
  Term 'max_elapsed': 0 hits [CLEAN]
  Term 'deadline': 0 hits [CLEAN]
  Term 'total retry': 0 hits [CLEAN]
  Term 'retry budget': 0 hits [CLEAN]
  Term 'max_delay': 0 hits [CLEAN]
  Term 'across all attempts': 0 hits [CLEAN]
  Term 'across retries': 2 hit(s) [ALL CLEARED AS IRRELEVANT]
    - 6d61f021e1b376c4 (fault-tolerance.mdx#inspect-retry-state) [CLEARED]
      Reason: Describes runtime.execution_info.node_first_attempt_time being constant across retries; does not cap cumulative retry wall-clock time.
    - 1b9a02395c8dcdd2 (use-graph-api.mdx#access-execution-info-inside-a-node) [CLEARED]
      Reason: Describes runtime.execution_info.node_first_attempt_time staying the same across retries; does not cap cumulative retry wall-clock time.

Item: q044 - Which built-in checkpointer class connects directly to a Neo4j graph database instance?
  Term 'neo4j': 0 hits [CLEAN]

Item: q045 - How do I configure raw WebSocket server framing and endpoint handlers in langgraph.json?
  Term 'websocket': 0 hits [CLEAN]
  Term 'web socket': 0 hits [CLEAN]
  Term 'socket': 0 hits [CLEAN]

Item: q046 - Which InMemorySaver argument caps how many checkpoints are kept per thread?
  Term 'max_checkpoints': 0 hits [CLEAN]
  Term 'retention': 1 hit(s) [ALL CLEARED AS IRRELEVANT]
    - 16da86313b94feae (persistence.mdx#checkpoints-growing-unboundedly) [CLEARED]
      Reason: Discusses pruning checkpoints and cron retention for PostgresSaver; no retention argument for InMemorySaver exists.
  Term 'ttl': 3 hit(s) [ALL CLEARED AS IRRELEVANT]
    - 22ae4759d4f0aa55 (graph-api.mdx#node-caching) [CLEARED]
      Reason: Describes CachePolicy(ttl=...) for node caching, unrelated to InMemorySaver checkpoint retention.
    - 1eabea8372a39087 (use-functional-api.mdx#caching-tasks) [CLEARED]
      Reason: Describes CachePolicy(ttl=120) task caching in Functional API, unrelated to InMemorySaver.
    - 485938d00611014a (use-graph-api.mdx#add-node-caching) [CLEARED]
      Reason: Describes CachePolicy(ttl=120) node caching in StateGraph, unrelated to InMemorySaver.

Item: q047 - How do I swap in a modified node function on an already-compiled graph without recompiling it?
  Term 'hot swap': 0 hits [CLEAN]
  Term 'hot-swap': 0 hits [CLEAN]
  Term 'replace node': 0 hits [CLEAN]
  Term 'reload': 0 hits [CLEAN]

Item: q048 - How do I export an existing StateGraph definition into a GraphQL mutation schema?
  Term 'graphql': 0 hits [CLEAN]

Item: q049 - Which setting runs each graph node in its own Kubernetes Pod?
  Term 'kubernetes': 0 hits [CLEAN]
  Term 'k8s': 0 hits [CLEAN]
  Term 'pod': 0 hits [CLEAN]
  Term 'pods': 0 hits [CLEAN]
  Term 'executor': 0 hits [CLEAN]

Item: q050 - How do I track dollar cost and token billing per node attempt using execution_info?
  Term 'billing': 5 hit(s) [ALL CLEARED AS IRRELEVANT]
    - 8910a2ee2e6eceae (thinking-in-langgraph.mdx#start-with-the-process-you-want-to-automate) [CLEARED]
      Reason: Example customer email topic ('billing issue') in email triage agent tutorial.
    - 9f8b395e2fca69e3 (thinking-in-langgraph.mdx#keep-state-raw-format-prompts-on-demand) [CLEARED]
      Reason: Intent classification literal ('billing') in email triage tutorial.
    - b16ab7e8fc45f76f (thinking-in-langgraph.mdx#implementing-our-email-agent-nodes) [CLEARED]
      Reason: Routing condition matching email classification intent == 'billing'.
    - f9f8d48e79be1134 (thinking-in-langgraph.mdx#try-out-your-agent) [CLEARED]
      Reason: Tutorial test scenario running email agent with a billing issue.
    - 88b3b001108649f3 (use-subgraphs.mdx#subgraph-persistence) [CLEARED]
      Reason: Illustrative customer support subagent role ('billing expert').
  Term 'cost': 4 hit(s) [ALL CLEARED AS IRRELEVANT]
    - f0cfdf3abbe906d0 (checkpointers.mdx#durability-modes) [CLEARED]
      Reason: Idiomatic phrase: 'at the cost of some performance overhead' in durability modes.
    - b4199820f7d508c6 (frontend/custom-stream-channels.mdx#use-cases) [CLEARED]
      Reason: Bullet point listing custom frontend stream channel use cases, not execution_info.
    - 24e76416b458ca31 (pregel.mdx#deltachannel) [CLEARED]
      Reason: Idiomatic phrase: 'at the cost of larger checkpoints' in DeltaChannel docs.
    - 485938d00611014a (use-graph-api.mdx#add-node-caching) [CLEARED]
      Reason: Idiomatic phrase: 'expensive (either in terms of time or cost)' in node caching.
  Term 'token usage': 2 hit(s) [ALL CLEARED AS IRRELEVANT]
    - e2bc10ee4e354945 (event-streaming.mdx#messages) [CLEARED]
      Reason: Describes streaming event field for message-finish events, not execution_info.
    - b4199820f7d508c6 (frontend/custom-stream-channels.mdx#use-cases) [CLEARED]
      Reason: Lists token usage among hypothetical live metrics for custom frontend stream channels.
  Term 'dollar': 0 hits [CLEAN]

=================================================
Overall Result: PASSED (All unanswerable terms have zero uncleared hits)
```

5. Mechanical audit (`py tasks.py audit-eval`):
```text
Audit completed: written to C:\Users\Bilal Aamir\Documents\GitHub\RAG Docs Assistant\data\eval\AUDIT.md
Summary: 42 answerable items | Unresolved evidence: 0 | must_mention failures: 0 | Grounding flags: 0 | 4-gram overlaps: 0 | Noisy evidence: 3 | Version proof failures: 0
```

6. Pytest test suite (`py tasks.py test`):
```text
................................................                         [100%]
48 passed in 1.19s
```

7. Linter and formatting (`py tasks.py lint`):
```text
All checks passed!
58 files already formatted
Running ruff check...
Running ruff format --check...
```

8. Dataset Composition Summary:
| Category | Count | Proportion | Target | IDs |
|---|---|---|---|---|
| single | 28 | 56.0% | 28 | q001-q008, q010-q028, q039 |
| multi | 8 | 16.0% | 8 | q029-q036 |
| version | 6 | 12.0% | 6 | q009, q037, q038, q040-q042 |
| unanswerable | 8 | 16.0% | 8 | q043-q050 |
| Total | 50 | 100.0% | 50 | q001-q050 |

- Distinct documentation pages used: 27 pages (maximum items per page: 5; cap is <= 5)
- Real user source share: 11 / 42 answerable items (26.2%)
- Human verification status: 50 / 50 items marked verified (100.0%)

Decisions made
- (a) Real-source threshold lowered from 20 to 11 (MIN_REAL_SOURCES = 11 in src/ragdocs/eval/config.py): Explicit human decision on 2026-10-21. Under a strict evidence standard requiring an authentic original-poster sentence matching a saved page snapshot on the identical problem, only 11 of 42 answerable items could be verified. Lowering the threshold avoided fabricating or padding sources. (See D14 in docs/DECISIONS.md)
- (b) Benchmark characterized as mostly documentation-derived: With 11 of 42 answerable items (26.2%) real-sourced, 31 answerable items and all 8 unanswerables are documentation-derived. The benchmark is formally described as mostly synthetic, engineered for documentation coverage under strict anti-leakage constraints. (See D14 in docs/DECISIONS.md)
- (c) Validation machinery extended to 11 checks: Added unanswerable keyword absence checking with human-adjudicated clearance (data/eval/absence_adjudication.json), evidence-only must_mention enforcement against each item's own evidence chunks (including version items), case-insensitive 4-gram overlap checking, and registered verbatim source-quote verification. (See D16 in docs/DECISIONS.md)
- (d) Unanswerable absence checking methodology: Validated via plain-keyword regex matching with word boundaries (`(?<![A-Za-z0-9_])term(?![A-Za-z0-9_])`). Any hit on chunks.jsonl must be formally reviewed and adjudicated as irrelevant in absence_adjudication.json. (See D16 in docs/DECISIONS.md)
- (e) Scoring semantics separation: In dataset validation (validate-eval), must_mention is checked case-sensitively against evidence chunks to enforce ground-truth naming precision. In downstream pipeline evaluation (M05, M07), the answer scorer should evaluate must_mention case-insensitively and treat must_mention presence as a soft signal alongside a generative LLM answer judge. (See D15 in docs/DECISIONS.md)
- (f) Evaluation set freeze: The evaluation dataset (data/eval/eval_set.jsonl) is frozen at git tag eval-set-v1. Any subsequent modification requires a new version tag (eval-set-v2), a new DECISIONS entry, and re-running all recorded baseline metrics. (See D15 in docs/DECISIONS.md)

Deviations from the prompt
- Real-source minimum adjusted: The plan's initial requirement of 20 real user sources was reduced to 11 via human decision when strict same-problem matching showed that only 11 authentic threads existed in the audited corpus.
- Validator checks expanded: 11 validation checks are implemented instead of the 9 in the original plan. `must_mention` for version items is checked against each item's own evidence chunks rather than anywhere across the corpus.
- Additional audit and verification files: Added scripts/check_unanswerable.py, scripts/audit_eval.py, scripts/verify_source_quotes.py, data/eval/absence_terms.json, data/eval/absence_adjudication.json, data/eval/source_quotes.json, and local data/eval/source_snapshots/ to enforce automated verification.
- Task runner: Native Windows 11 environment uses `py tasks.py <command>` instead of `make` (per AGENTS.md rule 9 and D12). No Makefile is present in the repository.
- Commit structure: The human reviewer created commit af9d098 ("M03: draft eval set") and final sign-off commit c92688d ("M03: eval set v1 (50 items, 50/50 verified, 11/42 real-sourced)") tagged eval-set-v1.

Known issues and limitations
- Mostly synthetic benchmark: Only 11 of 42 answerable items (26.2%) originate from real developer forum/issue threads; the remaining 31 answerable items are documentation-derived.
- Generic identifier signal strength: Generic identifiers in `must_mention` (e.g. `messages`, `nodes`, `StateGraph`, `stream_events`) are weak discriminators on their own and require pairing with an LLM judge.
- Multi-hop evidence noise: Three items resolve to multiple chunks under their section anchors: q031 (6 chunks), q032 (4 chunks), and q036 (4 chunks). This broad anchor resolution blurs chunk-level retrieval precision metrics.
- Version items documentation boundary: The pinned documentation corpus describes current APIs only; older deprecated patterns (e.g. `NodeInterrupt`, `subgraphs=True`) cannot be verified from corpus text alone and rely on external release proof URLs recorded in notes.
- Absence search term completeness: Keyword absence validation depends on the selected terms in absence_terms.json; unindexed synonyms could hypothetically appear in corpus text.
- `source_snapshots/` local exclusion: data/eval/source_snapshots/ is excluded via .gitignore. On a fresh clone, `py tasks.py verify-sources` and the validator's "Source quotes verified" check fail until snapshot text files are restored locally.

Open questions for the human
- None. All 5 open-item decisions were resolved, verified against the corpus, and approved.

Proposed follow-ups (out of scope)
- [NOT DONE] Graceful snapshot degradation: Allow the validator's "Source quotes verified" check to emit a warning rather than failing when data/eval/source_snapshots/ is absent on fresh clones, while retaining strict verification in `verify-sources`.
- [NOT DONE] Chunk-level gold IDs: Add optional chunk ID resolution alongside `(doc_path, anchor)` pairs to enable fine-grained retrieval evaluation.
- [NOT DONE] Scorer specification for M07: Implement fuzzy case-insensitive token matching in the M07 answer scorer rubric.

Prerequisites for the next module
- Git tag `eval-set-v1` exists on commit `c92688dd35816e0133517033f53db22d3b233396` (verified via `git tag -l`).
- Human sets `GEMINI_API_KEY` in `.env` (required for M04 embeddings index build).
- `data/processed/chunks.jsonl` present and unchanged from M02.
