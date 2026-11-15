# Architecture and Engineering Decisions

### D1 Repository Structure
- **Decision:** Monorepo architecture for all three pipelines.
- **Choice:** Monorepo, shared core, one deployment; tags `v1-baseline` and `v2-agentic`.
- **Reason:** Enables direct comparison across pipelines on identical corpora, indexes, and evaluation sets.

### D2 Deployment Target
- **Decision:** Target serverless deployment platform.
- **Choice:** Everything on Vercel (static UI + FastAPI Python function).
- **Reason:** Free tier hosting with serverless functions and CDN static file delivery.
- **Gate:** In M01: bundle over 400 MB or cold start over 10 s means backend moves to a Hugging Face Docker Space.
- **Gate Decision (M01):** PASS. Local bundle-check: 223.19 MB; Vercel function bundle: 76.0 MB compressed, 230.7 MB uncompressed (limit 400 MB). First live /api/health call: 1.13 s (limit 10 s); runtime dependency import probe: 1876.04 ms.

### D3 Frontend Technology
- **Decision:** User interface build stack.
- **Choice:** Static HTML/CSS/vanilla JS frontend, no build step.
- **Reason:** Zero compilation dependencies, instant deployment, and minimal bundle footprint.

### D4 Index Architecture
- **Decision:** Index format and runtime loading strategy.
- **Choice:** Index built offline and shipped in the bundle; in-memory numpy search behind a VectorIndex interface.
- **Reason:** Avoids dedicated vector database hosting overhead while providing microsecond local retrieval.

### D5 Embeddings Provider and Model
- **Decision:** Text representation model and dimensionality.
- **Choice:** Gemini embeddings API at 768 dimensions with separate document and query task types.
- **Reason:** High-quality semantic embeddings matching asymmetric retrieval tasks.

### D6 Reranking Strategy
- **Decision:** Two-stage retrieval reranking.
- **Choice:** Cohere Rerank behind a Reranker interface with a no-op option.
- **Reason:** State-of-the-art cross-encoder reranking to boost top-k precision.
- **Gate:** In M05: under 3 questions of hit@5 gain means rerank is disabled in production.
- **Gate Decision (M05):** FAIL (reranking disabled in production, `use_reranker = False`). On the 42-question benchmark, `hybrid` hit@5 is 34/42 (81.0%) and `hybrid_rerank` hit@5 is 35/42 (83.3%). Gain is 1 question (35 - 34 = 1), which is under the 3-question threshold. Furthermore, reranking degraded Hit@1 from 22/42 (52.4%) to 17/42 (40.5%) and MRR from 0.631 to 0.575. Consequently, `Settings.use_reranker` defaults to `False` in production, using `NoopReranker`.

### D7 Generation and Evaluation Models
- **Decision:** LLM providers for generation, grading, and offline judge.
- **Choice:** Groq for generation and grading; Gemini Flash as eval judge (different model family). Model IDs live only in config.
- **Reason:** Fast inference on Groq for interactive latency and model family diversity for unbiased evaluation.

### D8 Web Search Fallback
- **Decision:** Web search tool for corrective retrieval.
- **Choice:** Tavily web search restricted to the official docs domain as the corrective fallback.
- **Reason:** Restricts external grounding strictly to authoritative technical documentation.

### D9 Evaluation Methodology
- **Decision:** Evaluation metrics and judge design.
- **Choice:** Custom evaluation: deterministic retrieval metrics plus a rubric LLM judge, audited by hand on 10 items.
- **Reason:** Balances reproducible retrieval metrics with nuanced semantic accuracy evaluation.

### D10 Rate Limiting
- **Decision:** Protection against API abuse and cost overruns.
- **Choice:** Upstash Redis rate limiting (per-IP hourly window + global daily cap); disabled with a warning when env vars are absent.
- **Reason:** Prevents quota exhaustion on free tier serverless endpoints.

### D11 Documentation Corpus
- **Decision:** Corpus boundaries and version stability.
- **Choice:** Corpus: LangGraph Python docs only, one pinned commit.
- **Reason:** Ensures stable URLs, reproducible chunking, and deterministic ground-truth verification.

### D12 Development on native Windows
- **Decision:** Cross-platform developer ergonomics across Windows, CI, and Vercel.
- **Choice:** tasks.py instead of make, .gitattributes LF, utf-8 IO helpers.
- **Reason:** The project folder lives on Windows, while CI and Vercel run Linux.

## Decisions added during development

### D13 Runtime Dependency Source on Vercel
- **Decision:** Vercel ignores `pyproject.toml` via `.vercelignore` so it installs runtime dependencies from `requirements.txt`, which stays the single source of runtime dependencies.
- **Choice:** Add `pyproject.toml` to `.vercelignore`.
- **Reason:** Vercel's runtime package loader (`@vercel/python-analysis` in `loadPythonManifest`, verified at `https://github.com/vercel/vercel/blob/main/packages/python-analysis/src/manifest/package.ts#L426-L460` and `https://vercel.com/docs/functions/runtimes/python`) prioritizes `pyproject.toml` over `requirements.txt`. Since `pyproject.toml` has `dependencies = []` by project design, ignoring `pyproject.toml` causes Vercel to install dependencies from `requirements.txt`.

### D14 Real-Source Threshold for the Evaluation Set
- **Decision:** Minimum required proportion of real user questions in the 50-item evaluation benchmark.
- **Choice:** Lower minimum from 20 to 11 (`MIN_REAL_SOURCES = 11` in `src/ragdocs/eval/config.py`). An item qualifies as real-sourced only when `data/eval/source_quotes.json` contains a verbatim original-poster sentence matching a saved page snapshot and addressing the exact same technical problem.
- **Reason:** Strict same-problem verification against thread snapshots identified only 11 genuine problem matches out of 42 answerable items (26.2%). The evaluation dataset is formally characterized as mostly synthetic (31 of 42 answerable items and all 8 unanswerable items are documentation-derived) to maintain strict anti-leakage and factual accuracy standards without padding.
- **Date:** 2026-10-21

### D15 Eval Set Freeze and Scoring Semantics
- **Decision:** Versioning policy and evaluation scoring semantics for `data/eval/eval_set.jsonl`.
- **Choice:** Freeze `data/eval/eval_set.jsonl` at git tag `eval-set-v1` following M03 completion. Any subsequent modification requires a new version tag (`eval-set-v2`), a new entry in `docs/DECISIONS.md`, and re-running all recorded baseline metrics. In downstream retrieval and generation evaluation (M05, M07), answer scorers must evaluate `must_mention` identifiers case-insensitively and treat identifier presence as a soft signal alongside a generative LLM answer judge.
- **Reason:** All three RAG pipelines share this evaluation set for direct comparability; changing test items after establishing baselines invalidates historical comparisons.
- **Date:** 2026-10-22

### D16 Eval-Set Validation Extensions and Snapshot Handling
- **Decision:** Dataset validation checks and thread snapshot storage.
- **Choice:** Implement 11 automated validation checks in `src/ragdocs/eval/validate.py`, including keyword absence verification for unanswerable items with an explicit human-adjudicated clearance file (`data/eval/absence_adjudication.json`), evidence-only `must_mention` verification against an item's own evidence chunks (including version items), case-insensitive 4-gram overlap prevention, and registered verbatim quote verification. Store raw third-party thread HTML/text snapshots in `data/eval/source_snapshots/` which is excluded via `.gitignore`, while committing short attributed quotes and URLs in `data/eval/source_quotes.json`.
- **Reason:** Guarantees tamper-proof ground-truth validation offline while preventing redistribution of scraped third-party forum content in the repository. Fresh repository clones require local snapshot retrieval before running `verify-sources`.
- **Date:** 2026-10-22

### D17 Embedding Model and Offline Index Format
- **Decision:** Embedding model selection, vector storage format, and rate-limit batching strategy.
- **Choice:** Use `gemini-embedding-001` with `output_dimensionality=768` (L2-normalised by caller). Store dense vectors as float16 (`vectors.f16.npy`, 829.6 KB), chunk metadata in identical row order (`chunk_meta.jsonl`), pre-tokenized BM25 token lists (`bm25.json`), and verified file hashes (`manifest.json`). Cache embeddings via `diskcache` in `cache/embeddings` using SHA-1 keys. Cap API batches at 100 texts and 20,000 tokens with tenacity exponential backoff to respect free-tier 30k TPM rate limits.
- **Reason:** `text-embedding-004` was decommissioned by Google as of 2026-01-14; `gemini-embedding-001` is the current stable production model supporting Matryoshka dimension reduction to 768. Float16 format saves 50% memory footprint while maintaining numerical stability for runtime dot product search without torch or external vector database dependencies.
- **Date:** 2026-10-22

### D18 LangSmith Role
- **Decision:** What LangSmith is used for and how tracing is configured across runs.
- **Choice:** LangSmith provides tracing for local and eval runs. Each eval run is uploaded as a LangSmith experiment on dataset `ragdocs-eval-set-v1` by replaying stored results; committed run folders stay the source of truth. Every run of every pipeline uses the same tracing setting, recorded in `config.json`. RAGAS scoring runs with tracing off. Production tracing is off by default; enabling it requires a sampling rate of 0.1 or lower.
- **Reason:** Traces help debugging and experiment comparison, but committed results must not depend on an external service, and the tracing setting must not vary between compared runs.
- **Date:** 2026-11-15

### D19 RAGAS Role
- **Decision:** How RAGAS is used next to the custom judge.
- **Choice:** RAGAS runs alongside the custom judge, with a split of duties:
  - Deterministic metrics: retrieval hits, abstention, hallucination on unanswerables.
  - Custom judge (audited): correctness 0 to 2 and answer-level citation support.
  - RAGAS: faithfulness, response relevancy, context precision with reference, context recall.
  - RAGAS scores answerable items only. Faithfulness and relevancy skip abstained answers. Every metric reports its n and a paired view.
  - The RAGAS LLM is Gemini. RAGAS is a dev-only dependency behind a pip dry-run gate, with an isolated-venv fallback.
  - Noise rule for continuous metrics: per paired item, a win or loss is a difference over 0.2; report "no measurable difference" unless wins minus losses is 3 or more.
- **Reason:** Each metric family covers what it measures reliably; the noise rule prevents over-reading small differences on a 50-item set.
- **Date:** 2026-11-15

### D20 Citation Scoring
- **Decision:** How citations are scored given that the model often omits inline [n] markers (see M06 open question 1).
- **Choice:** The shared answer prompt stays unchanged. `citation_support` = 1 when every cited excerpt supports at least one claim in the answer and no central claim lacks a cited excerpt; 0 otherwise. The UI lists numbered Sources and renders [n] only when present.
- **Reason:** Citations are carried by the structured `cited` list; scoring at answer level avoids depending on inline markers.
- **Date:** 2026-11-15

### D21 Module Order
- **Decision:** Order of the remaining modules.
- **Choice:** M07 tracing, M08 harness and judge, M09 RAGAS and experiments with tag `v1-baseline`, then M10 corrective, M11 self-RAG (tag `v2-agentic`), M12 API, M13 UI, M14 deploy, M15 write-up.
- **Reason:** Tracing and evaluation are in place before the agentic pipelines, so their runs are traced and scored the same way as the baseline.
- **Date:** 2026-11-15

### D22 Context Metrics
- **Decision:** How context-based metrics are labelled and compared across pipelines.
- **Choice:** For corrective and self-RAG, contexts are the chunks the grader kept plus web results, so metrics computed on contexts (`context_hit@5`, `context_evidence_recall@5`, RAGAS context precision and recall) partly measure the grader's filtering. They are labelled "on contexts given to the generator". `first_retrieval_hit@5`, computed from each run's first retrieval event, is the like-for-like retrieval comparison across pipelines.
- **Trace naming:** Pipeline parent runs are named after the pipeline, the LangGraph run inside them is named "graph", and retrieval runs are named "hybrid_retrieve", so no run nests under one with the same name.
- **Reason:** Keeps retrieval comparisons fair across pipelines that filter contexts differently.
- **Date:** 2026-11-15
