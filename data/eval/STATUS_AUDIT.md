# Eval Set Hardening Audit (Part A Report)

**Date:** 2026-10-20  
**Repository State:** main branch, 7 modified files, 9 untracked files from prior session.  
**Auditor:** Antigravity (Medium)

---

## 1. Checklist Audit

| Phase | Item / Requirement | Status | Evidence / Details |
|---|---|---|---|
| **Phase 0** | 50 lines, sequential `q001`..`q050`, category counts 28/8/6/8 | **DONE** | `data/eval/eval_set.jsonl`: exactly 50 lines; `single=28, multi=8, version=6, unanswerable=8`. Verified via script. |
| **Phase 0** | `q009` category == "version"; `q039` category == "single" | **DONE** | `eval_set.jsonl`: `q009` is `version`, `q039` is `single`. |
| **Phase 0** | `q033` has "stream.subgraphs" and not "subgraphs=True" | **DONE** | `eval_set.jsonl`: `reference_answer` has `stream.subgraphs`, no `subgraphs=True`. |
| **Phase 0** | `q034` reference answer does not contain "Command" | **DONE** | `eval_set.jsonl`: `reference_answer` contains `get_state` and `update_state`, no `Command`. |
| **Phase 0** | `q046` question starts with "Which InMemorySaver argument" | **DONE** | `eval_set.jsonl`: question is `"Which InMemorySaver argument caps how many checkpoints are kept per thread?"`. |
| **Phase 0** | Count of items with `verified: true` is 0 | **DONE** | Verified via script: `verified: true` count = 0. All 50 items have `verified: false`. |
| **Phase 0** | List every item whose `source` is not "docs", with URL | **DONE** | Exactly 8 items: `q001`, `q002`, `q004`, `q006`, `q007`, `q011`, `q018`, `q038` (listed in Section 4 below). |
| **Phase 1** | `data/eval/absence_terms.json` exists & covers all 8 unanswerables | **DONE** | Covers `q043`..`q050` with plain-word keyword lists. |
| **Phase 1** | `src/ragdocs/eval/absence.py` regex boundary, case-insensitive, snippets | **DONE** | `build_term_regex` uses `(?<![A-Za-z0-9_])pattern(?![A-Za-z0-9_])`, `re.IGNORECASE`, extracts ~200-char context snippet. |
| **Phase 1** | `data/eval/absence_adjudication.json` exists with clearance rule | **DONE** | Exists, maps `q046` (4 entries) and `q050` (11 entries) with item id, term, chunk_id, verdict "irrelevant", and reason. |
| **Phase 1** | `scripts/check_unanswerable.py` exists, exits nonzero on uncleared hits | **DONE** | Exists, returns exit code 1 on uncleared hits. |
| **Phase 1** | `tasks.py` has `check-unanswerable` command | **DONE** | Command `check-unanswerable` wired in `tasks.py` lines 86-93. |
| **Phase 1** | `validate.py` has 10th check "Unanswerable absence" | **DONE** | Check 10 in `src/ragdocs/eval/validate.py` lines 270-291, 354-361. |
| **Phase 1** | Pytest unit tests for absence machinery | **DONE** | `tests/test_validate_eval.py` has 6 tests covering word boundary, case-insensitivity, multi-word terms, uncleared hit failure, adjudicated pass, missing terms failure. |
| **Phase 2** | `notes` of `q043`..`q050` formatted with real search results | **DONE** | All 8 notes have canonical format `"Plain-keyword search over chunks.jsonl (2026-10-14): ... Rationale: ... Hits adjudicated irrelevant: ..."` |
| **Phase 2** | Absence search re-run matches notes counts | **DONE** | Re-run in this session via `py tasks.py check-unanswerable` matched all counts exactly. Zero uncleared hits. |
| **Phase 2** | Hit adjudication audit & review of `q045`, `q046`, `q047`, `q049` | **DONE** | Evaluated chunk texts. `q046` hits are PostgreSQL cron retention or cache TTL (not `InMemorySaver`); `q045`, `q047`, `q049` have 0 hits. None is answerable. |
| **Phase 3** | `audit.py`, `scripts/audit_eval.py`, `tasks.py audit-eval`, `AUDIT.md` exist | **DONE** | All 4 files exist and run cleanly without error. |
| **Phase 3** | `must_mention` is EVIDENCE-ONLY in `validate.py` | **DONE** | `validate.py` lines 240-268 checks that identifier is present in that item's evidence chunk texts only; tested in `test_must_mention_evidence_only`. |
| **Phase 3** | 4-word overlap check lowercases before comparing, with test | **DONE** | `tokenize_words` lowercases and strips punctuation; tested in `test_4gram_overlap_case_insensitive`. |
| **Phase 3** | Reference-answer grounding implemented and verified | **DONE** | Implemented in `audit.py`. Ran over all 42 answerable items; 0 grounding flags found (q024 verified with `Annotated` and `operator.add` in chunk text). |
| **Phase 3** | Evidence noise (>3 chunks) and page spread reports | **DONE** | Reported in `AUDIT.md`: 4 noisy items (`q018`, `q031`, `q032`, `q036`); 27 distinct pages, max 5 items per page. |
| **Phase 3** | Version items notes contain Proof URL / docs requirement | **DONE** | All 6 items (`q009`, `q037`, `q038`, `q040`, `q041`, `q042`) contain GitHub release proof URLs. |
| **Phase 4** | 11 ticked URLs live verified in browser / HTTP | **PARTIAL** | Recorded in `SOURCES_LOG.md` by previous session, but requires live opening and verification in THIS session per non-negotiable ground rules. |
| **Phase 5** | Real-source count >= 20 of 42 answerable items | **PARTIAL** | Currently only 8/42 answerable items are sourced from real user threads. Shortfall of 12 items. `validate-eval` fails on Check 7. |
| **Phase 6** | `REVIEW.md` regenerated and reflects latest notes | **DONE** | `REVIEW.md` generated on 10/14/2026 2:35 PM (newer than `eval_set.jsonl`), shows canonical keyword search notes for `q043`..`q050`. |
| **Phase 6** | `README.md` documents all rules and composition | **DONE** | `data/eval/README.md` describes composition table, schema, absence check, evidence-only must_mention, case-insensitive 4-gram, and real-source rule. |

---

## 2. Baseline Command Outputs

### 2.1 `py tasks.py validate-eval`
```text
=== Evaluation Dataset Validation Report ===
[PASS] Parse as EvalItem: Successfully parsed 50 items
[PASS] IDs unique and sequential: IDs are unique and exactly q001..q050
[PASS] Category composition: Category counts exact: single=28/28, multi=8/8, version=6/6, unanswerable=8/8
[PASS] Evidence resolution: All evidence references resolve to existing chunks
[PASS] No 4-word overlap: No 4-word overlap found between questions and evidence chunks
[PASS] Page spread: Page spread rules satisfied (27 pages used; max items per page: 5)
[FAIL] Real user question sourcing: Only 8/42 answerable items from user sources (minimum 20 required)
[PASS] Must-mention identifiers: All must_mention identifiers verified verbatim in evidence chunks
[PASS] Verification status: 0/50 items marked verified
[PASS] Unanswerable absence: All unanswerable items have zero uncleared keyword hits
============================================
Overall Result: FAILED
```

### 2.2 `py tasks.py validate-eval --require-verified`
```text
=== Evaluation Dataset Validation Report ===
[PASS] Parse as EvalItem: Successfully parsed 50 items
[PASS] IDs unique and sequential: IDs are unique and exactly q001..q050
[PASS] Category composition: Category counts exact: single=28/28, multi=8/8, version=6/6, unanswerable=8/8
[PASS] Evidence resolution: All evidence references resolve to existing chunks
[PASS] No 4-word overlap: No 4-word overlap found between questions and evidence chunks
[PASS] Page spread: Page spread rules satisfied (27 pages used; max items per page: 5)
[FAIL] Real user question sourcing: Only 8/42 answerable items from user sources (minimum 20 required)
[PASS] Must-mention identifiers: All must_mention identifiers verified verbatim in evidence chunks
[FAIL] Verification status: Verification required but only 0/50 items marked verified
[PASS] Unanswerable absence: All unanswerable items have zero uncleared keyword hits
============================================
Overall Result: FAILED
```

### 2.3 `py tasks.py check-unanswerable`
```text
=== Unanswerable Absence Verification Report ===

Item: q043 - How do I configure CUDA device pinning so graph nodes run on designated GPUs?
  Term 'cuda': 0 hits [CLEAN]
  Term 'gpu': 0 hits [CLEAN]
  Term 'device_map': 0 hits [CLEAN]

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

### 2.4 `py tasks.py audit-eval`
```text
Audit completed: written to C:\Users\Bilal Aamir\Documents\GitHub\RAG Docs Assistant\data\eval\AUDIT.md
Summary: 42 answerable items | Unresolved evidence: 0 | must_mention failures: 0 | Grounding flags: 0 | 4-gram overlaps: 0 | Noisy evidence: 4 | Version proof failures: 0
```

### 2.5 `py tasks.py test`
```text
........................................                                 [100%]
40 passed in 2.54s
```

### 2.6 `py tasks.py lint`
```text
All checks passed!
52 files already formatted
Running ruff check...
Running ruff format --check...
```

---

## 3. Prioritised Remaining Work for Part B

1. **Live URL Verification (B4):**
   - Open and verify the 11 candidate/proof URLs live in this session.
   - Confirm page loads, page title, and whether the content genuinely supports the target item.
   - Verify rejection of Stack Overflow #10 (JS SDK) and #11 (legacy model memory).
   - Record exact findings in `data/eval/SOURCES_LOG.md`.

2. **Real-Source Sourcing Hunt (B5):**
   - The dataset currently has only 8 verified real-sourced answerable items (`q001`, `q002`, `q004`, `q006`, `q007`, `q011`, `q018`, `q038`).
   - Sourcing target is 20 / 42 answerable items (shortfall of 12).
   - Investigate genuine user threads on `forum.langchain.com`, GitHub issues/discussions (`langchain-ai/langgraph`), or Stack Overflow for candidate topics (`q003`, `q005`, `q008`, `q010`, `q012`, `q013`, `q014`, `q015`, `q016`, `q017`, `q019`, `q020`, `q021`, `q022`, `q023`, `q025`, `q026`, `q027`, `q028`, `q029`, `q030`, `q031`, `q033`, `q034`, `q035`, `q036`, `q039`).
   - For every candidate thread found: open it, verify match, ensure question stays answerable from existing evidence, check 4-gram overlap, update `eval_set.jsonl` source and question if adapted, and log in `SOURCES_LOG.md`.
   - If fewer than 20 can be verified, stop and report the exact count without padding.

3. **Regeneration and Validation (B6):**
   - Re-run `.venv\Scripts\python scripts/make_review_sheet.py` to keep `REVIEW.md` synchronized.
   - Run `tasks.py validate-eval`, `tasks.py check-unanswerable`, `tasks.py audit-eval`, `tasks.py test`, `tasks.py lint`.
   - Update `data/eval/README.md` if any schemas or counts change.
