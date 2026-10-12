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
