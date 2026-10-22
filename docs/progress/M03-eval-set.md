M03: Eval set
Status: Partial
Date: 2026-10-21

Goal
Draft data/eval/eval_set.jsonl with exactly 50 items, implement the validator, absence checking machinery, mechanical audit, human review sheet, verify all constraints (category counts, page spread, identifier presence, absence of 4-word overlap, unanswerable absence clearance, and verbatim-verified real user sources), and stop for human review.

What was built
- src/ragdocs/eval/config.py: configuration constants for evaluation dataset validation, defining MIN_REAL_SOURCES = 11 (lowered by human decision from 20 on 2026-10-21).
- src/ragdocs/eval/validate.py: core validation rules enforcing 11 checks including evidence-only must-mention identifiers, case-insensitive 4-gram overlap, category counts, page spread, real user question sourcing (MIN_REAL_SOURCES = 11), keyword absence for unanswerable items, and registered source quotes verification.
- src/ragdocs/eval/verify_sources.py: verbatim source quote verification engine checking URL match, snapshot file existence, normalized contiguous substring matching without ellipses, author presence in snapshot, non-title check, and minimum length (>=40 chars).
- src/ragdocs/eval/absence.py: keyword absence scanning logic using word-boundary regex (`(?<![A-Za-z0-9_])term(?![A-Za-z0-9_])`), context snippet extraction, and adjudication clearance checking.
- src/ragdocs/eval/audit.py: mechanical audit engine evaluating evidence resolution, evidence-only must-mention presence, reference-answer code token grounding, noise reporting (>3 chunks), and version proof URL checking.
- src/ragdocs/eval/review.py: human review sheet markdown generator formatting questions, reference answers, identifiers, evidence chunks, and keyword absence notes.
- scripts/validate_eval.py: CLI validator checking eval_set.jsonl with utf-8-sig encoding and reporting 11 pass/fail checks.
- scripts/verify_source_quotes.py: CLI verifying that every non-"docs" source matches a contiguous verbatim OP quote in source_quotes.json backed by a snapshot file.
- scripts/check_unanswerable.py: CLI checking unanswerable item absence terms across chunks.jsonl, reporting cleared vs uncleared hits and exiting nonzero on uncleared hits.
- scripts/audit_eval.py: CLI running mechanical audit and writing data/eval/AUDIT.md.
- scripts/make_review_sheet.py: CLI generating data/eval/REVIEW.md from eval_set.jsonl and chunks.jsonl.
- tasks.py: wired commands `validate-eval`, `verify-sources`, `check-unanswerable`, and `audit-eval`.
- tests/test_validate_eval.py: pytest tests covering overlap detection, unresolved evidence, wrong category counts, unanswerable constraint validation, require-verified flag, evidence-only must-mention enforcement, MIN_REAL_SOURCES threshold enforcement, and complete absence check suite.
- tests/test_verify_source_quotes.py: pytest tests covering exact substring pass, paraphrase failure, curly-quote normalization pass, title-as-quote failure, missing snapshot failure, wrong author failure, and registration check.
- data/eval/source_snapshots/: plain UTF-8 text snapshots of all inspected source threads (thread title, author, post position, and post text).
- data/eval/source_quotes.json: machine-checkable evidence dictionary with url, verified author, post position, contiguous verbatim OP quote, and access date for all 11 verified items.
- data/eval/absence_terms.json: keyword search terms for all 8 unanswerable items (q043..q050).
- data/eval/absence_adjudication.json: formal adjudication records clearing irrelevant corpus matches for q046 and q050.
- data/eval/SOURCES_LOG.md: live audit and sourcing log recording verified verbatim quotes, corrections table, reverted sources, rejected threads, and verified version release URLs.
- data/eval/SOURCE_SPOTCHECK.md: spotcheck audit table and corrections section generated programmatically from source_quotes.json.
- data/eval/STATUS_AUDIT.md: audit log of previous session state and baseline results.
- data/eval/README.md: complete documentation on composition, schema definitions, absence checking, and review process.
- data/eval/eval_set.jsonl: hardened evaluation dataset of 50 items across single (28), multi (8), version (6), and unanswerable (8) categories, with 11 verbatim-verified user sources and verified=false on all items.
- data/eval/REVIEW.md: formatted human review sheet for all 50 items.

How to run
- Run source verifier: `py tasks.py verify-sources`
- Run validator: `py tasks.py validate-eval`
- Run validator requiring all 50 verified: `py tasks.py validate-eval --require-verified`
- Run unanswerable absence check: `py tasks.py check-unanswerable`
- Run mechanical audit: `py tasks.py audit-eval`
- Regenerate review sheet: `.venv\Scripts\python scripts/make_review_sheet.py`
- Run test suite: `py tasks.py test`
- Run linter: `py tasks.py lint`

Verification
1. Source quote verification (`py tasks.py verify-sources`):
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

2. Validator report (`py tasks.py validate-eval`):
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
   [PASS] Verification status: 0/50 items marked verified
   [PASS] Unanswerable absence: All unanswerable items have zero uncleared keyword hits
   [PASS] Source quotes verified: All 11 external source(s) have registered quotes and snapshots
   ============================================
   Overall Result: PASSED
   ```

3. Validator enforcement check (`py tasks.py validate-eval --require-verified`):
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
   [FAIL] Verification status: Verification required but only 0/50 items marked verified
   [PASS] Unanswerable absence: All unanswerable items have zero uncleared keyword hits
   [PASS] Source quotes verified: All 11 external source(s) have registered quotes and snapshots
   ============================================
   Overall Result: FAILED
   ```

4. Unanswerable keyword absence check (`py tasks.py check-unanswerable`):
   ```text
   =================================================
   Overall Result: PASSED (All unanswerable terms have zero uncleared hits)
   ```

5. Mechanical audit report (`py tasks.py audit-eval`):
   ```text
   Audit completed: written to data/eval/AUDIT.md
   Summary: 42 answerable items | Unresolved evidence: 0 | must_mention failures: 0 | Grounding flags: 0 | 4-gram overlaps: 0 | Noisy evidence: 3 | Version proof failures: 0
   ```

6. Test suite (`py tasks.py test`):
   ```text
   ................................................                         [100%]
   48 passed in 1.68s
   ```

7. Linter and formatting (`py tasks.py lint`):
   ```text
   All checks passed!
   58 files already formatted
   Running ruff check...
   Running ruff format --check...
   ```

Decisions made
- Strict Verbatim Evidence Standard: Every non-"docs" item must be backed by a contiguous verbatim quote written by the thread's OP (or an OP reply for q011) in data/eval/source_quotes.json, matching character-for-character against a plain UTF-8 text snapshot in data/eval/source_snapshots/<id>.txt.
- Reversion of Unverifiable Threads: `q002` (Stack Overflow OP wrote only code and an error pointer; no problem sentence), `q025` (GitHub issue asked why conditional node expects dict when returning string; RELATED TOPIC ONLY), and `q038` (quote asked how to map user answers to state on resume, whereas item asked basic Command(resume=...) pattern; RELATED TOPIC ONLY) were reverted to "docs".
- Finalized Real-Source Baseline: Established MIN_REAL_SOURCES = 11 in `src/ragdocs/eval/config.py` as an explicit human decision on 2026-10-21. The dataset contains 11 verified real user sources and 31 documentation-derived answerable sources (mostly synthetic benchmark).
- Added 11th Validator Check: "Source quotes verified" in `src/ragdocs/eval/validate.py` ensures any non-"docs" source has an entry in `source_quotes.json` and a corresponding snapshot file in `source_snapshots/`.

Deviations from the prompt
None. All instructions and ground rules followed strictly.

Known issues and limitations
- `verified: false` remains on all 50 items pending human review in `data/eval/REVIEW.md`.

Open questions for the human
- None. Ready for human review of REVIEW.md.

Proposed follow-ups (out of scope)
- Human review of `data/eval/REVIEW.md` and flipping `verified: true`.

Prerequisites for the next module
- Human review and approval of the evaluation set items.
