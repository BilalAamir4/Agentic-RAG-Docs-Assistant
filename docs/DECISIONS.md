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
- **Update (M08, 2026-11-16): judge model chosen by free-tier budget.** Free-tier limits are not published in readable form (https://aistudio.google.com/docs/rate-limits says limits "can be viewed in Google AI Studio"; https://console.groq.com/docs/rate-limits shows Developer-plan base limits), so values come from the human's AI Studio project page and Groq org limits page (Free plan), read on 2026-11-15:
  - gemini-3.6-flash 5 RPM / 250K TPM / 20 RPD; gemini-2.5-flash-lite 10 / 250K / 20; gemini-3.1-flash-lite 15 / 250K / 500; gemini-3.5-flash-lite 15 / 250K / 500.
  - Groq openai/gpt-oss-120b, openai/gpt-oss-20b and qwen/qwen3.8-27b: 30 RPM / 1K RPD / 8K TPM / 200K TPD. llama-3.3-70b-versatile is not on the org's limits page (treated as unavailable).
  - Rule (human): first model that supports with_structured_output, is not an OpenAI gpt-oss model, and has RPD of at least 500 (one pipeline's judge plus RAGAS in about one day). gemini-3.1-flash-lite and gemini-3.5-flash-lite both qualify; the human chose **gemini-3.5-flash-lite** (newer, same limits). structured_output True in langchain-google-genai 4.4.1 data/_profiles.py; one live with_structured_output call succeeded on 2026-11-15 with usage_metadata present.
  - gemini-3.6-flash was rejected: 20 RPD means up to 3 days for 42 judge calls, and RAGAS (about 400 calls per pipeline) would take about 20 days.
  - M09 uses gemini-3.1-flash-lite as ragas_llm_model with its own 15 RPM / 500 RPD budget (AI Studio limits are per model).
  - Settings: judge_model = gemini-3.5-flash-lite, judge_rpm_limit = 15, judge_rpd_limit = 500, judge_tpm_limit = 250000, judge_quota_timezone = America/Los_Angeles (Google resets RPD at midnight Pacific).
- **Update (M08, 2026-11-16): Groq daily token budget.** Free plan caps each gpt-oss model at 200K tokens per day; 50 items at the 3,000-token starting estimate is about 150K. Settings.groq_tpd_limit = 200000 for openai/gpt-oss-120b and openai/gpt-oss-20b; RollingBudget enforces tokens_per_day next to requests_per_day, both persisted per model in cache/budget.json, and raises DailyLimitReached (exit code 3) when either daily limit would be exceeded. Groq's daily reset time is not documented on the pages read; the budget assumes UTC midnight.

- **Update (M08, 2026-11-16): Groq daily limits as a draining bucket, and budget recording (human decisions).**
  - Groq's daily limits are not a UTC calendar day. Evidence: the rerun results/runs/baseline-20261116-1050 got ten 429 "tokens per day (TPD): Limit 200000" responses (its failed_attempts.jsonl). Each retry-after equals (Used + Requested - 200,000) / (200,000 / 86,400 s) to 0.1 s:

    | UTC | Used | Requested | Over | Formula | Groq retry-after |
    |---|---|---|---|---|---|
    | 11:01:26 | 197,585 | 2,562 | 147 | 63.5 s | 1m3.504s |
    | 11:01:27 | 197,584 | 2,562 | 146 | 63.1 s | 1m3.072s |
    | 11:01:30 | 197,576 | 2,897 | 473 | 204.3 s | 3m24.336s |
    | 11:01:31 | 197,575 | 2,897 | 472 | 203.9 s | 3m23.904s |
    | 11:03:34 | 199,850 | 2,259 | 2,109 | 911.1 s | 15m11.088s |
    | 11:03:35 | 199,847 | 3,370 | 3,217 | 1,389.7 s | 23m9.744s |
    | 11:03:38 | 199,840 | 2,259 | 2,099 | 906.8 s | 15m6.768s |
    | 11:03:38 | 199,839 | 2,259 | 2,098 | 906.3 s | 15m6.336s |
    | 11:03:42 | 199,832 | 2,259 | 2,091 | 903.3 s | 15m3.312s |
    | 11:03:42 | 199,831 | 2,259 | 2,090 | 902.9 s | 15m2.880s |

  - Choice (human): model each Groq daily limit as a bucket. Balance = recorded usage drained at limit / 86,400 s (tokens 200,000 / 86,400 = 2.315/s; requests 1,000 / 86,400 = 0.0116/s); available = limit x 0.9 (throttle_safety) - balance. Settings.groq_quota_window = "token_bucket". The balance is computed from the per-call events in cache/budget.json ({"version": 2, "events": {model: [[t, requests, tokens]]}}, 2-day retention). Gemini models keep the calendar day in America/Los_Angeles. "rolling_24h" remains available as the fallback.
  - Backstop (human): on any 429 the eval runner waits for the provider's retry-after (default 60 s when none is given; pause with exit code 3 if longer than 1,800 s or after 3 waits per item). A per-day 429 while the model predicted room is a model miss, logged in cache/budget_model_misses.jsonl and copied to the tracking file. At 2 misses the run pauses; the human rule is then to revert groq_quota_window to "rolling_24h" and report.
  - Gemini Embedding 1 limits (AI Studio, 1 Day view, 2026-11-16): 100 RPM, 30K TPM, 1K RPD (Settings.embedding_*). Embedding tokens are estimated as characters / 4; the API reports none.
  - Every live Groq or Gemini call is recorded: ragdocs.eval.budget_recorder.install_budget_recorder registers a BudgetRecorder through langchain_core's register_configure_hook (every chat-model call in the process; failed calls as one request with 0 tokens) and as a usage listener that GeminiEmbedder notifies on every API attempt. Installed by the eval and judge runners, scripts/ask.py, build_index.py, eval_retrieval.py, structured_output_check.py, and every test marked live (tests/conftest.py). Cohere rerank is not recorded: use_reranker is False, so nothing calls it.
  - `py tasks.py budget [--need MODEL=TOKENS[:REQUESTS]]` prints each model's balance or window usage, free, and free at 0.9; with --need it exits 1 and prints when the need fits. Rule (human, also in AGENTS.md): run it before any live run or check and stop if the need does not fit.
  - cache/budget.json for 2026-11-16 was rebuilt from evidence (per-item UUIDv7 run-id times, failed_attempts.jsonl, the structured-output check file, judge_v1.jsonl mtime), plus one reconciliation event of 18,730 tokens at 11:01:26Z so the gpt-oss-120b bucket balance equals Groq's reported Used 197,585 at that time (unlogged failed calls and earlier usage).

### D8 Web Search Fallback
- **Decision:** Web search tool for corrective retrieval.
- **Choice:** Tavily web search restricted to the official docs domain as the corrective fallback.
- **Reason:** Restricts external grounding strictly to authoritative technical documentation.
- **Update (M10 S1, 2026-11-20): implementation.** src/ragdocs/providers/websearch.py TavilySearch (tavily-python 0.8.5) sends include_domains=[Settings.docs_domain], max_results=Settings.web_max_results (3), search_depth="basic" (1 credit). include_domains_mode is left at its server default, "restrict" (https://docs.tavily.com/documentation/api-reference/endpoint/search). A defensive filter also drops any result whose host is not docs_domain or a subdomain and reports the drops (WebSearchOutcome.dropped_off_domain). 429 and 5xx are retried (3 attempts, 1 s then 2 s); a missing TAVILY_API_KEY fails at construction because tavily-python otherwise falls back to keyless mode. Live probe (3 queries, 9 URLs): all on docs.langchain.com; 2 of 9 were outside the ingested LangGraph corpus (oss/python/langchain, oss/python/deepagents), and none carried an #anchor.

### D9 Evaluation Methodology
- **Decision:** Evaluation metrics and judge design.
- **Choice:** Custom evaluation: deterministic retrieval metrics plus a rubric LLM judge, audited by hand on 10 items.
- **Reason:** Balances reproducible retrieval metrics with nuanced semantic accuracy evaluation.
- **Update (M08, 2026-11-16): judging decoupled from generation.** `py tasks.py eval --pipeline NAME` generates answers and computes deterministic scores only and never calls the judge (verdict is None in per_question.jsonl). `py tasks.py judge --run-dir DIR` scores the stored answers and writes judge_v<N>.jsonl ({id, verdict, judge_model, judge_prompt_version, usage, cached}) with N = Settings.judge_prompt_version; it is resumable and exits with code 3 at the judge's daily cap. The same command is the re-judge path after a prompt version bump. report.py, compare_runs, judge_audit, the M09 experiment upload and every later reader take each item's verdict from the highest judge_v<N>.jsonl present (else per_question.jsonl) and record that effective version. Reason: Groq generation never waits on judge quota, and re-judging never regenerates answers.
- **Judge (M08):** one call per answerable, non-abstained item returns JudgeVerdict(correctness 0/1/2, citation_support 0/1, rationale of at most 60 words). JUDGE_PROMPT is in src/ragdocs/eval/prompts.py; judge_prompt_version = 1.
- **Audit gate (M08):** correctness agreement of at least 8/10 and citation_support agreement of at least 8/10 on 10 items (seed 21; 6 single, 2 multi, 2 version). Result: passed, see the 2026-11-18 audit result below (gate changed to 80% over 11 items).
- **Update (M08, 2026-11-17, human): audit adds low-scored items.** The seed-21 draw of 10 is kept; every other judged item with judge correctness below 2 is added to the audit, flagged "added: judge score < 2" (stratification by judge score, not a redraw), so the audit checks the judge where it marks answers down. The gate becomes at least 80% agreement on each column over all audited items, ceil(0.8 x n): 9 of 11 for run baseline-20261116-1050 (q024 added). Settings.eval_audit_add_below_correctness = 2, Settings.eval_audit_gate_rate = 0.8; `py tasks.py judge-audit --score` prints the gate result.
- **Audit result (M08, 2026-11-18): gate passed.** Run results/runs/baseline-20261116-1050, judge gemini-3.5-flash-lite, prompt version 1, 11 items (seed-21 ten plus q024). `py tasks.py judge-audit --score`: correctness agreement 10/11, citation_support agreement 10/11, "gate (80% on each column, 9/11): PASS". Disagreements: q006 citation_support judge 0 / human 1; q031 correctness judge 2 / human 1 (the answer omits the different-schema pattern, which the question needs).
  - Label provenance (human): Bilal labelled 8 of the 11 items; Claude labelled all 11 independently; the 3 disagreements between the two were resolved by reasoning item by item; the 3 items Bilal did not label use Claude's labels. The human approved the final labels.
  - Labelling rules: correctness, a missing reference fact lowers the score only if the question needs it; citation_support, the structured CITED list is the citation (D20), inline [n] markers are not required.
  - faithful (for M09): no on q016 (invented final code line), q033 (a claim about the root stream outputting the parent's tokens is in no excerpt) and q024 (cause stitched from unrelated excerpts [1] and [3]; reducer fix missing); yes on the other 8.
  - Judge citation check: the only citation_support 0 item in this run is q006. Its answer has no inline [n] markers but its structured CITED list holds excerpt [2], and the judge's rationale says it "did not provide any citations", so the 0 comes from the missing inline markers, against D20. In the earlier run 0919 the citation_support 0 items were q024 and q034 (both with inline markers; the rationales name excerpts that do not support a claim) and q025 (no inline markers; rationale about a wrong claim only). Judge prompt version 1 stays: one marker-driven error in 39 judged items is within the gate; a prompt change would need version 2 and a re-judge (proposed follow-up in M08).
- **Update (M08, 2026-11-18, human): judge prompt version 2 (citation flags).** JUDGE_PROMPT adds one rule under citation_support: the CITED / NOT CITED flags on the excerpts are the answer's citations, and inline [n] markers are optional and must not affect citation_support (D20). The rest of the rubric is unchanged. Settings.judge_prompt_version = 2.
  - Re-judge: `py tasks.py judge --run-dir results/runs/baseline-20261116-1050` wrote judge_v2.jsonl (39/39 items, 0 cached, 88,544 tokens; answers not regenerated; judge_v1.jsonl kept). The only verdict that changed from v1 is q006: (2, 0) to (2, 1), rationale "supported by excerpt 2".
  - Audit re-scored against the v2 verdicts with the same human labels (no new labelling): correctness agreement 10/11, citation_support agreement 11/11, "gate (80% on each column, 9/11): PASS". The remaining disagreement is q031 (judge 2 / human 1). The judge columns printed in results/judge_audit.md still show the v1 verdicts it was written from; scoring always uses the effective (highest) judge version.
  - Run of record summary under v2: correct 38/42 (unchanged), citation_support 39/39 (v1: 38/39).
  - Run baseline-20261116-0919 was not re-judged and still has only judge_v1.jsonl, so compare refuses to pair it with run 1050 (effective judge_prompt_version differs).

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
- **Update (M09, 2026-11-18): dependency gate failed; isolated venv (path A, human decision).**
  - Gate: latest stable ragas is 0.4.4 (PyPI upload 2026-11-14, requires_python >=3.9). `pip install --dry-run --report` into .venv would change three packages pinned in requirements.txt: tenacity 9.1.4 -> 8.5.0, langchain-core 1.6.10 -> 1.8.2, langsmith 0.14.7 -> 0.15.0 (no torch, transformers or sentence-transformers). With every pin as a constraint pip also resolves, but only by backtracking to instructor 0.4.8, typer 0.9.4 and langchain 1.4.6; that fallback was not used.
  - Choice: path A. requirements-ragas.txt pins the full set that resolved in a clean Python 3.12 venv from ragas==0.4.4, langchain-google-genai and diskcache (105 lines; langchain-google-genai 4.5.0, langchain-core 1.8.2, instructor 1.3.2). `py tasks.py ragas-setup` creates .venv-ragas (gitignored); requirements.txt and requirements-dev.txt are unchanged.
  - Handoff: scripts/export_ragas_input.py (main venv, ragdocs.eval.ragas_export) writes <run>/ragas_input.jsonl with id, category, user_input, response, retrieved_contexts (stored order), reference and per-metric eligibility flags (population rules above). tools/ragas_score.py (.venv-ragas, no ragdocs imports) reads only that file plus cache/budget.json and writes ragas_config.json, ragas_scores.jsonl and ragas_summary.json. `py tasks.py ragas --run-dir DIR` runs both; scripts/ragas_run.py passes every setting on the command line and the Gemini key only in the child's environment (read through Settings).
  - API: ragas 0.4.4 legacy single-turn metrics (Faithfulness, ResponseRelevancy with strictness 3, LLMContextPrecisionWithReference, LLMContextRecall) with LangchainLLMWrapper(ChatGoogleGenerativeAI, bypass_n=True) and LangchainEmbeddingsWrapper. The newer ragas.metrics.collections classes accept only instructor-based LLMs and, for Gemini, need instructor.from_genai, which the resolved instructor 1.3.2 lacks. The legacy import paths are marked deprecated (removal planned for ragas 1.0); the version is pinned.
  - Models: LLM gemini-3.1-flash-lite (15 RPM, 250K TPM, 500 RPD, its own quota, D7), embeddings gemini-embedding-001 (shares the 1,000 RPD embedding budget). LangSmith tracing and ragas telemetry (RAGAS_DO_NOT_TRACK) are off inside the tool.
  - Budget: the tool follows the D24 file contract, checks per-item needs before calls and exits with code 3 at a daily cap.
  - Paired view (human decision, 2026-11-18): the noise rule applies in both directions ("better (+N)" or "worse (-N)" when wins minus losses or losses minus wins is 3 or more; thresholds in Settings.compare_paired_threshold and compare_noise_margin). Paired metrics: correctness (0 to 2, abstained = 0), context_evidence_recall@5, must_mention coverage and the four RAGAS metrics, over items scored in every compared run.
  - Presentation (human decision, 2026-11-18; applies to results/summary.md now and the M15 README): the count-based correctness verdict (items better versus worse, net 3 needed) is the primary correctness result; the paired correctness means are supporting detail; must_mention coverage is labelled a soft signal (D15).
  - Request discipline (human instructions after day 1, 2026-11-18): one request at a time. tools/ragas_score.py SequentialLLM sends response_relevancy's n = strictness = 3 generations as 3 sequential requests, each with its own retry; ragas's bypass_n batch sent them concurrently and retried all 3 on one failure. Every LLM and embedding request waits for a per-minute window capped at Settings.ragas_rpm_ceiling (12). Every failed attempt and metric error is logged with its full exception chain to cache/ragas_errors.jsonl. Probe on q009: all four metrics scored; the only failures were transient 503 UNAVAILABLE ("high demand"), all retried.
  - n = 3 emulation: ResponseRelevancy with strictness 3 asks for 3 generations (n = 3). gemini-3.1-flash-lite rejects multiple candidates ("400 INVALID_ARGUMENT: Multiple candidates is not enabled for this model"), so n = 3 is emulated as 3 sequential single requests with the same prompt and temperature. Observed on the full run (cache/ragas_relevancy_generations.jsonl): the first 3 items scored (q011, q012, q013) each had 2 distinct questions out of 3; 7 of 29 items had 3 identical questions. The generations are therefore not fixed, and the strictness = 3 average is not equivalent to a single generation.
  - Error rule: the 10% rule counts final metric failures only (after ragas's retries); retried transient failures (for example 503 UNAVAILABLE) are reported separately from cache/ragas_errors.jsonl.
  - Faithfulness validity (Step 4 sanity check failed; human decision, option 2 after an audit, 2026-11-19):
    - On the 11 audited items, mean RAGAS faithfulness was 0.896 for the 8 labelled faithful and 0.963 for the 3 labelled not faithful. RAGAS disagreed with the human labels on those 3 items: q016 1.0, q033 1.0, q024 0.889.
    - Evidence (results/runs/baseline-20261116-1050/ragas_faithfulness_audit.jsonl, the statements and verdicts of a rescore that reproduced every stored score):
      - RAGAS faithfulness checks prose statements and does not evaluate code blocks. q016's code block became 3 descriptive statements ("The provided Python code demonstrates ..."), and its invented line `print(items.value["text"]) # → "I love pizza"` was never checked. q033's code block produced no statement.
      - Unsupported prose can still pass by inference: q033 "The root stream outputs the tokens of the parent agent" got verdict 1 ("implying ...").
      - Literal NLI verdicts and statement paraphrase lowered two items labelled faithful: q006 0.5 ("edit" became "overwrite"; "without running any node" got verdict 0) and q028 0.667 ("Pregel uses the LastValue channel by default" got verdict 0 because the context says LastValue is the default channel type).
    - Setup was checked and is not the cause: all 50 rows pass exactly the stored context_texts (equal to the index chunk text, code intact, untruncated).
    - The q006 and q033 human labels were judgement calls (Claude's labels; see the D9 audit provenance).
    - Presentation: RAGAS faithfulness is labelled "prose-level grounding signal" in summaries and compare, shown next to the judge's correctness and citation_support. It is not a check of code correctness and is not used alone as a hallucination verdict. The faithfulness model is unchanged.
  - Cache: cache/ragas is shared by every run of the tool whatever --out-dir is; keys are sha1 of the D19 key fields only. `py tasks.py ragas --run-dir DIR --cache-check` reports hits and remaining needs from the cache without API calls.

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
- **Update (M10 S1, 2026-11-20): computation.** ragdocs.eval.report.first_retrieval_hit_at_5 takes the item's first `retrieval` TraceEvent, resolves its top 5 chunks to (doc_path, anchor) by chunk_id in data/index/chunk_meta.jsonl, else by ragdocs.docs_urls.url_to_doc_ref(url), and applies hit_at_k against the gold evidence; an answerable item with no retrieval event is a miss. The baseline's stored retrieval event has url but no chunk_id, so for pipeline "baseline" the value is computed from its contexts (equal by construction: all 50 items have one retrieval event whose 5 URLs equal the 5 context URLs in order; the URL path gives the same values). Baseline: 34/42 for both metrics. Agentic pipelines (S2) must emit chunk_id and url for every chunk in the retrieval event. summary.md and compare show the row "first-retrieval hit@5 (like-for-like retrieval)" directly above context_hit@5, and the LangSmith experiment carries feedback key first_retrieval_hit_at_5.
- **Date:** 2026-11-15

### D23 Structured Output Method for Groq Calls
- **Decision:** How Groq gpt-oss calls request structured output (AnswerDraft now; the M10/M11 grader calls later).
- **Choice:** `with_structured_output(schema, method="json_schema", strict=True)` (Settings.structured_output_method = "json_schema", structured_output_strict = True), replacing the default `method="function_calling"`. The M10 and M11 grader calls on openai/gpt-oss-20b must use the same method through the same settings. The answer prompt text is unchanged.
- **Evidence:**
  - Groq: strict json_schema (constrained decoding) is supported for openai/gpt-oss-20b and openai/gpt-oss-120b (https://console.groq.com/docs/structured-outputs). langchain-groq 1.1.3 `with_structured_output` passes `response_format={"type": "json_schema", "json_schema": {..., "strict": true}}` only for models in `_STRICT_STRUCTURED_OUTPUT_MODELS` (both gpt-oss models) and parses with PydanticOutputParser. `convert_to_json_schema(AnswerDraft, strict=True)` lists all three fields as required with `additionalProperties: false`.
  - Before: the first baseline run (results/runs/baseline-20261116-0919, function_calling) paused 3 times on Groq `400 tool_use_failed` (wrong tool name `answer_draft` or `json`, or no tool call); at least 6 failed calls over 50 items.
  - Same-input comparison (scripts/structured_output_check.py, results/structured_output_check-20261116.json, 2026-11-16): 10 eval questions (q015, q028, q001 to q008), same retrieved contexts and messages, one call per method, alternating order. function_calling 2/10 failed (q002 "Failed to parse tool call arguments as JSON"; q008 tool `answerDraft`); json_schema strict 0/10 failed. On the 8 questions where both succeeded, abstain matched 8/8 and cited lists matched 7/8 (q007 [1, 4, 5] vs [1, 4]). Tokens per successful call were about 8% higher with json_schema.
  - The sample is small (10 calls per method); the decision also rests on the mechanism: constrained decoding produces schema-valid JSON and has no tool name to get wrong.
  - After (2026-11-17, full 50-item rerun results/runs/baseline-20261116-1050): structured_output_failures 0 over 50 items (the function_calling run had at least 6 failed calls and 3 pauses).
  - Observed, not attributed to the method: false_abstention rose from 1/42 (q029) to 3/42 (q029, plus q008 and q025, which the function_calling run answered: q008 judged (2, 1), q025 judged (0, 0)). The net change is 2 items, inside the 3-item noise margin of the D19 noise rule, so it is not attributed to json_schema. Other observed changes: correct 38/42 in both runs; citation_support 38/41 to 38/39.
- **Measurement:** every eval run records `structured_output_failures` per item (failed attempts before success, from <run>/failed_attempts.jsonl, so counts survive pauses) and `rate_limited_attempts` (attempts that failed with RateLimitError, counted separately), and summary.md reports both.
- **Reason:** The function-calling failures surface to users as error events, and the eval had been scoring only the attempt that succeeded, which hid the failure rate.
- **Date:** 2026-11-16
- **Update (M11 S1, 2026-11-21): failed attempts are counted by kind.** M10 found that structured_output_failures counted every failed attempt that was not a 429 (runner.py build_record), so corrective's q043 (a Tavily connection error) was counted as a structured-output failure.
  - Kinds (ragdocs.providers.errors): structured_output (groq 400 with body error.code json_validate_failed, OutputParserException, pydantic ValidationError), rate_limit, transient (connection, timeout, 5xx), permanent (auth, plan limit, other 4xx), unclassified.
  - New runs store FailedAttempt.kind. It comes from the agentic error event's data["error_kind"] (the message stays the class name), or from the message when the event has none (baseline).
  - The report recomputes every count from the stored attempts. structured_output_failures counts only structured_output. New per-item fields and summary rows: transient_call_errors, permanent_call_errors, unclassified_call_errors. A stored message that does not identify a kind on its own (a bare "BadRequestError" or "WebSearchError") is unclassified.
  - results/error_reclassifications.json holds evidence-backed overrides for stored attempts (human decision). The report applies them after message classification, and every summary that uses one carries a note. Run folders are never rewritten. Entries: corrective-20261120-1852 q049 structured_output (M10 S3 additional facts 3: json_validate_failed) and q043 transient (M10 S3 Step 1: ConnectionError, status None).
  - Effect: corrective structured_output_failures 2 -> 1 (items 2/50 -> 1/50), transient 0 -> 1. Both baseline runs are unchanged.

### D24 Budget File Contract
- **Decision:** One on-disk format for cache/budget.json, written by both the main venv (ragdocs.eval.throttle.BudgetStore, BudgetRecorder) and the isolated RAGAS venv (tools/ragas_budget.py).
- **Format:** `{"version": 2, "events": {"<model id>": [[t, requests, tokens], ...]}}`.
  - t: Unix epoch seconds as a float rounded to 3 decimals; requests and tokens: non-negative integers. A failed call is one request with 0 tokens; embedding tokens are characters / 4 (the API reports none).
  - Events per model are sorted by t. Every write drops events older than 2 days (172,800 s).
  - Serialised as JSON with indent 2, ensure_ascii False, UTF-8, LF and one trailing newline.
  - A file without `"version": 2` is migrated by the main venv only (BudgetStore); the RAGAS tool refuses it and asks for `py tasks.py budget` to be run first.
  - One process writes the file at a time (the main-venv wrapper does not call APIs while the tool runs).
- **Windows:** Groq models use the token bucket (D7); Gemini models use the calendar day in America/Los_Angeles; caps are daily limit x throttle_safety (0.9).
- **Test:** tests/test_ragas_export.py writes the same events with both writers and asserts byte-identical files, cross-reads them, and checks that both compute the same daily usage, cap and reset time.
- **Reason:** The API budget rule (AGENTS.md, D7) needs every live call from either environment in one file.
- **Date:** 2026-11-18

### D25 Decision Event Outcome Contract
- **Decision:** How the UI and tests classify decision TraceEvents.
- **Choice:** Every TraceEvent of type "decision" sets data["outcome"] to exactly one of "ok", "retry", "stop" or "info" (ragdocs.pipelines.agentic.state.OUTCOMES). The UI colours decisions from this field only, never from message text.
- **Corrective mapping (M10):**
  - grade_documents "k of n chunks relevant": "ok" when the accumulated relevant chunks reach Settings.min_relevant_chunks, else "retry" (also on a grading parse failure, which the message names).
  - grade_documents routing event ("Route to <branch>: <reason>", data.branch): "ok" for generate, "retry" for rewrite_query and web_search.
  - rewrite_query "query rewritten" (data.old_query, data.new_query): "retry".
  - web_search "fell back to web search" (data.urls): "retry" when it returned results, "stop" when it returned none.
  - generate: "info" when generating ("Generating from k graded excerpts and m web results"); "stop" when there are no contexts and the pipeline abstains without an LLM call.
- **Trace naming addition:** the Tavily call inside the web_search node runs as "tavily_search" (run_type tool), so it does not nest under the node run of the same name (D22; human choice, M10 S2).
- **Reason:** One machine-readable field lets M13 colour every decision consistently across corrective and self-RAG, and lets tests assert routing without parsing messages.
- **Date:** 2026-11-20

### D26 Self-RAG Structured-Call Failure Policy
- **Decision:** What self_rag does when one of its new structured LLM calls (decide_retrieval, verify_answer, regenerate) fails.
- **Choice:**
  - decide_retrieval fails: needs_docs = true, and the decision event has outcome "info". Reason: retrieving costs at most one extra retrieval and a grading call, while skipping retrieval on a broken decision would answer without documentation.
  - verify_answer fails (on the first or the second verification): keep the current answer, record the failure, outcome "info", route to END. Never abstain because a check broke. Reason: a broken check is not evidence that the answer is wrong.
  - regenerate fails: abstain with abstain_reason "regenerate_failed", outcome "stop". Reason: regenerate runs only after the verifier rejected the answer, so a failed regeneration leaves only an answer the verifier rejected.
  - No node retries a failed structured call.
  - Every caught failure counts in the item's structured_output_failures and is appended to PipelineResult.diagnostics["fallbacks"] as "decide_failed", "verify_failed" or "regenerate_failed". The decision event of the failed node also carries data["fallback"] with the same value, so the trace and the UI show it; the report reads diagnostics only.
  - Caught failures are exactly those for which ragdocs.providers.errors.is_structured_output_error is True. Rate-limit, auth and connection errors are not caught by these fallbacks and propagate exactly as in corrective (one error event; the eval runner's existing handling).
- **Storage:** PipelineResult.diagnostics (dict, default empty, left out of dumps when empty). Only self_rag copies graph-state diagnostics into it, so baseline and corrective results serialise byte-identically to M10.
- **Method:** the new calls use the D23 method (with_structured_output(schema, method="json_schema", strict=True) through Settings.structured_output_method and structured_output_strict).
- **Date:** 2026-11-21

### D27 Self-RAG LLM Call Bound
- **Decision:** The maximum number of LLM calls per self_rag question.
- **Choice:** With Settings.max_query_rewrites = 1 and Settings.max_regenerations = 1, the worst case is decide 1 + grade 2 + rewrite 1 + generate 1 + verify 2 + regenerate 1 = 8 calls. Fallbacks (D26) add no calls. Corrective's bound stays 4 (grade 2 + rewrite 1 + generate 1).
- **Reason:** A fixed bound keeps Groq quota planning and latency predictable, and tests can assert it.
- **Date:** 2026-11-21
