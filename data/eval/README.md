# Evaluation Dataset (`data/eval`)

## Purpose
The evaluation dataset is a curated benchmark of 50 test questions designed to evaluate retrieval and generation quality across all three RAG pipelines (baseline LangChain RAG, corrective RAG, and self-RAG in LangGraph). All pipelines share this exact eval set, ensuring direct comparability across architectures.

To prevent evaluation leakage, question texts never copy phrases from the documentation, and gold answers are anchored to stable `(doc_path, anchor)` pairs rather than transient chunk IDs.

## Dataset Composition

The dataset contains exactly 50 items distributed across four categories:

| Category | Count | IDs | Description | Evidence / Target |
|---|---|---|---|---|
| **single** | 28 | `q001` - `q008`, `q010` - `q028`, `q039` | Answered by a single section of one documentation page. | Exactly 1 `(doc_path, anchor)` |
| **multi** | 8 | `q029` - `q036` | Requires synthesizing information across 2 or more sections (from the same or different pages). | $\ge 2$ `(doc_path, anchor)` |
| **version** | 6 | `q009`, `q037`, `q038`, `q040` - `q042` | The current docs give an answer differing from older LangGraph versions (renamed/moved import, changed signatures, deprecated patterns). Questions are phrased neutrally. | Gold reference states current way; notes record outdated pattern & proof link. |
| **unanswerable** | 8 | `q043` - `q050` | Plausible LangGraph questions whose answer is absent from the corpus (unsupported feature, missing configuration, or third-party tool). | `reference_answer: None`, `evidence: []`, notes record keyword absence search results. |
| **Total** | **50** | `q001` - `q050` | - | - |

> [!NOTE]
> **Evaluation Set Sourcing Caveat**: Exactly 11 of the 42 answerable items (26.2%) are adapted from real user threads backed by verified verbatim OP quotes in `data/eval/source_quotes.json` and page snapshots. The remaining 31 answerable items and all 8 unanswerable items are documentation-derived. The dataset is therefore a mostly synthetic evaluation set designed to test comprehensive documentation coverage under strict anti-leakage constraints.

## Field Definitions (Schema: `EvalItem`)

- `id` (`str`): Unique identifier matching regex `^q\d{3}$` (`q001` to `q050`).
- `question` (`str`): Neutral developer inquiry formulated around a goal or error, free from docs headings.
- `category` (`Literal["single", "multi", "version", "unanswerable"]`): Category classification.
- `reference_answer` (`str | None`): 1 to 4 concise, factual sentences containing necessary API identifiers. `None` for unanswerable items.
- `evidence` (`list[Evidence]`): List of ground-truth `Evidence(doc_path=..., anchor=...)` objects. Empty for unanswerable items.
- `must_mention` (`list[str]`): 1 to 4 exact code identifiers (class, function, method, parameter) required in a correct answer. Empty for unanswerable items. Must appear verbatim in the item's own evidence chunks.
- `source` (`str`): URL of the verified real user question (GitHub issue, discussion, or Stack Overflow question) or `"docs"` if derived from documentation.
- `notes` (`str`): Context notes:
  - For version items: records the outdated answer, migration rationale, and proof URL.
  - For unanswerable items: records exact plain-keyword search results over `chunks.jsonl` in the canonical format:
    `Plain-keyword search over chunks.jsonl (<YYYY-MM-DD>): 'term1' (N matches), 'term2' (N matches), ... Rationale: <one sentence on why the corpus does not answer this>. Hits adjudicated irrelevant: <ids or none>.`
- `verified` (`bool`): Set to `true` once human review confirms correctness (50/50 items verified for eval-set-v1 sign-off).

## Sourcing, Absence, and Quality Rules

1. **Real User Sourcing**: A minimum of 11 of the 42 answerable items (`MIN_REAL_SOURCES = 11`, lowered from 20 by human decision on 2026-10-21 following strict verbatim problem matching) must be adapted from genuine user inquiries (Discourse forum, GitHub issues, or Stack Overflow questions). A source counts only with a verified verbatim OP quote in `data/eval/source_quotes.json` backed by a page snapshot in `data/eval/source_snapshots/`. Exactly 11 of 42 answerable items meet this criterion; the remaining 31 answerable items are documentation-derived, making this a mostly synthetic evaluation set. All investigated, adopted, reverted, and rejected candidate threads are documented in `data/eval/SOURCES_LOG.md` and `data/eval/SOURCE_SPOTCHECK.md`.
2. **Unanswerable Keyword Absence**: Every unanswerable item is mapped to keyword search terms in `data/eval/absence_terms.json`. Any keyword match across `chunks.jsonl` must be adjudicated as irrelevant in `data/eval/absence_adjudication.json` with a specific reason. Uncleared hits fail validation. Checked via `py tasks.py check-unanswerable`.
3. **Evidence-Only `must_mention`**: Every identifier in `must_mention` must appear verbatim (case-sensitive) in the text of that item's own evidence chunks (not the wider corpus).
4. **Reference-Answer Grounding**: All code-like tokens (functions, classes, arguments, decorators, filenames) in `reference_answer` must appear in the item's evidence chunk text.
5. **Case-Insensitive 4-Gram Overlap**: Questions and evidence chunks are tokenized by lowercasing, stripping `string.punctuation`, and splitting on whitespace. A question must share zero 4-grams with its evidence chunks.
6. **Page Spread**: Evidence spans at least 15 distinct documentation pages, with no single page supplying evidence for more than 5 items.
7. **Mechanical Audit**: Run `py tasks.py audit-eval` to generate `data/eval/AUDIT.md`, reporting per-item evidence resolution, evidence-only identifier presence, code grounding, overlap, and evidence noise.

## Scoring Semantics

- **Validator vs. Answer Scorer**: In dataset validation (`validate-eval`), `must_mention` identifiers are matched case-sensitively against evidence chunk text to ensure strict ground-truth accuracy.
- **Evaluation Scoring**: When evaluating pipeline responses, the downstream answer scorer should compare `must_mention` case-insensitively and treat `must_mention` presence as a soft signal alongside a generative answer judge rather than a hard binary gate.

## Review Procedure

1. Run `py tasks.py validate-eval` to confirm schema validity, page spread, identifier presence, and lack of word overlap.
2. Run `py tasks.py check-unanswerable` to verify keyword absence and clearance for unanswerable items.
3. Run `py tasks.py audit-eval` to verify evidence resolution, identifier presence, and reference answer grounding.
4. Generate the human review sheet: `.venv\Scripts\python scripts/make_review_sheet.py`.
5. Open `data/eval/REVIEW.md` and inspect each question, its reference answer, must-mention symbols, and retrieved evidence chunks.
6. Edit `data/eval/eval_set.jsonl` directly to fix any discrepancies and flip `verified: true` for approved items.
7. Verify that full dataset validation passes with enforcement: `py tasks.py validate-eval --require-verified`.

> **Note:** data/eval/source_snapshots/ is gitignored (it holds third-party page text). verify-sources and the 'Source quotes verified' check need those snapshots, so re-fetch the pages locally before running them. source_quotes.json keeps the short attributed quotes and URLs.
