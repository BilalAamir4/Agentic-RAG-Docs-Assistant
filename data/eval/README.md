# Evaluation Dataset (`data/eval`)

## Purpose
The evaluation dataset is a curated benchmark of 50 test questions designed to evaluate retrieval and generation quality across all three RAG pipelines (baseline LangChain RAG, corrective RAG, and self-RAG in LangGraph). All pipelines share this exact eval set, ensuring direct comparability across architectures.

To prevent evaluation leakage, question texts never copy phrases from the documentation, and gold answers are anchored to stable `(doc_path, anchor)` pairs rather than transient chunk IDs.

## Dataset Composition

The dataset contains exactly 50 items distributed across four categories:

| Category | Count | IDs | Description | Evidence / Target |
|---|---|---|---|---|
| **single** | 28 | `q001` - `q028` | Answered by a single section of one documentation page. | Exactly 1 `(doc_path, anchor)` |
| **multi** | 8 | `q029` - `q036` | Requires synthesizing information across 2 or more sections (from the same or different pages). | $\ge 2$ `(doc_path, anchor)` |
| **version** | 6 | `q037` - `q042` | The current docs give an answer differing from older LangGraph versions (renamed/moved import, changed signatures, deprecated patterns). Questions are phrased neutrally. | Gold reference states current way; notes record outdated pattern & proof link. |
| **unanswerable** | 8 | `q043` - `q050` | Plausible LangGraph questions whose answer is absent from the corpus (unsupported feature, missing configuration, or third-party tool). | `reference_answer: None`, `evidence: []`, notes contain keyword searches proving absence. |
| **Total** | **50** | `q001` - `q050` | - | - |

## Field Definitions (Schema: `EvalItem`)

- `id` (`str`): Unique identifier matching regex `^q\d{3}$` (`q001` to `q050`).
- `question` (`str`): Neutral developer inquiry formulated around a goal or error, free from docs headings.
- `category` (`Literal["single", "multi", "version", "unanswerable"]`): Category classification.
- `reference_answer` (`str | None`): 1 to 4 concise, factual sentences containing necessary API identifiers. `None` for unanswerable items.
- `evidence` (`list[Evidence]`): List of ground-truth `Evidence(doc_path=..., anchor=...)` objects. Empty for unanswerable items.
- `must_mention` (`list[str]`): 1 to 4 exact code identifiers (class, function, method, parameter) required in a correct answer. Empty for unanswerable items.
- `source` (`str`): URL of the real user question (GitHub issue, discussion, or Stack Overflow question) or `"docs"` if derived from documentation.
- `notes` (`str`): Context notes. For version items: records the outdated answer and migration link. For unanswerable items: records at least 3 keyword searches over `chunks.jsonl` confirming absence.
- `verified` (`bool`): Set to `true` once human review confirms correctness.

## Sourcing and Wording Rules

1. **Real User Sourcing**: At least 20 of the 42 answerable items are adapted from genuine user inquiries (GitHub issues/discussions or Stack Overflow questions).
2. **Developer-Centric Phrasing**: Questions reflect practical user goals or errors rather than documentation headings.
3. **No 4-Word Overlap**: A question must not share any sequence of 4 or more consecutive words (case-insensitive, punctuation stripped) with its evidence chunk texts.
4. **Verbatim Identifiers**: Every identifier in `must_mention` appears verbatim in the evidence chunks (or anywhere in the corpus for version items).
5. **Page Diversity**: Evidence spans at least 15 distinct documentation pages, with no single page supplying evidence for more than 5 items.

## Review Procedure

1. Run `py tasks.py validate-eval` to confirm schema validity, page spread, identifier presence, and lack of word overlap.
2. Generate the human review sheet: `.venv\Scripts\python scripts/make_review_sheet.py`.
3. Open `data/eval/REVIEW.md` and inspect each question, its reference answer, must-mention symbols, and retrieved evidence chunks.
4. Edit `data/eval/eval_set.jsonl` directly to fix any discrepancies and flip `verified: true` for approved items.
5. Verify that full dataset validation passes with enforcement: `py tasks.py validate-eval --require-verified`.
