M04: Index build
Status: Done
Date: 2026-10-22

Goal
Build dense vector and sparse BM25 retrieval indexes over data/processed/chunks.jsonl offline with disk caching, commit them to data/index/, provide runtime search interfaces without torch or vector database dependencies, and verify retrieval accuracy with sanity checks.

What was built
- src/ragdocs/config.py: Set Settings.embedding_model default to verified "gemini-embedding-001".
- requirements.txt: Moved tenacity==9.1.4 into runtime dependencies.
- requirements-dev.txt: Removed tenacity==9.1.4 from dev requirements.
- src/ragdocs/providers/embeddings.py: Runtime-safe GeminiEmbedder with token-aware batching, exponential backoff on 429/5xx, and L2 normalization.
- src/ragdocs/index/bm25_index.py: Runtime-safe tokenizer (snake_case, camelCase, 54 English stopwords) and BM25Index class.
- src/ragdocs/index/vector_index.py: Runtime-safe VectorIndex with float16 loading and dot product similarity search.
- src/ragdocs/index/loader.py: Runtime-safe LoadedIndex and load_index with manifest checksum validation and LRU caching via get_index.
- src/ragdocs/index/build.py: Offline index builder with diskcache in cache/embeddings, float16 vector export, BM25 tokens, and manifest generation.
- scripts/build_index.py: CLI script to build dense and sparse indexes reporting wall time, API calls, and checksums.
- tasks.py: Wired index command to run scripts/build_index.py with venv interpreter.
- tests/test_index.py: Unit tests for tokenizer cases, BM25 fixture ranking, VectorIndex search ordering, and loader tampered hash rejection.
- tests/test_embeddings_live.py: Live integration test verifying 768-dim query embedding and unit L2 norm within 1e-3.
- tools/index_sanity.py: Standalone retrieval sanity check evaluating BM25 top-1 and dense top-10 share over 100 sampled chunks.
- data/index/vectors.f16.npy: Float16 dense embedding matrix for 553 chunks (829.6 KB).
- data/index/chunk_meta.jsonl: Metadata lines for 553 chunks in identical row order (1527.0 KB).
- data/index/bm25.json: Pre-tokenized token structures for BM25Okapi (1254.2 KB).
- data/index/manifest.json: Index manifest with ISO timestamp, source commit, chunk counts, and file SHA-256 checksums.
- docs/DECISIONS.md: Appended D17 on embedding model, float16 vector format, and rate-limit batching strategy.
- docs/progress/PROGRESS.md: Updated M04 row status to Done with date and tracking file link.
- docs/progress/M04-index.md: Progress tracking document for module M04.

How to run
- Build index: `py tasks.py index`
- Run unit test suite: `py tasks.py test`
- Run live embeddings test: `py tasks.py test-live`
- Run linter and formatter: `py tasks.py lint`
- Compute index checksums: `py tasks.py hash data/index/vectors.f16.npy data/index/bm25.json`
- Run retrieval sanity check: `.venv\Scripts\python tools/index_sanity.py`
- Check deployment bundle size: `py tasks.py bundle-check`

Verification
1. Verification Table (Step 1 API & SDK Findings):
| Item | Verified Value | Source URL / Installed SDK File Path |
|---|---|---|
| Model ID | `gemini-embedding-001` (`text-embedding-004` shut down 2026-01-14, returns 404) | `https://ai.google.dev/gemini-api/docs/embeddings`<br>`.venv/Lib/site-packages/google/genai/models.py` |
| 768-dim config | `types.EmbedContentConfig(output_dimensionality=768)` | `https://ai.google.dev/gemini-api/docs/embeddings`<br>`.venv/Lib/site-packages/google/genai/types.py` (`EmbedContentConfig.output_dimensionality`) |
| Task types | `RETRIEVAL_DOCUMENT` (chunks), `RETRIEVAL_QUERY` (queries) | `https://ai.google.dev/gemini-api/docs/embeddings`<br>`.venv/Lib/site-packages/google/genai/types.py` (`EmbedContentConfig.task_type`) |
| Batch limit | 100 requests per payload (`at most 100 requests can be in one batch`) | `.venv/Lib/site-packages/google/genai/models.py`<br>API 400 error message on 101 items |
| Max input length | 2,048 tokens per text | `client.models.get(model='gemini-embedding-001').input_token_limit`<br>`https://ai.google.dev/gemini-api/docs/embeddings` |
| L2-normalisation | Required by caller (raw 768-dim vector norm is ~0.587-0.595) | Live API probe output: `np.linalg.norm(vec) = 0.5873`<br>`https://ai.google.dev/gemini-api/docs/embeddings` |
| Free-tier limits | 100 RPM, 30,000 TPM, 1,000 RPD | `https://ai.google.dev/gemini-api/docs/rate-limits`<br>Live 429 quota metric detail: `limit: 100`, `limit: 1000` |

2. Both Index Runs:
- Run 1 (`py tasks.py index` - fresh index build):
  * Chunks indexed: 553
  * Planned API batches: 11 payload calls (averaging 50.27 chunks per payload under the 20,000 token cap; average chunk token count is 286.3 tokens).
  * API calls made: 28 total HTTP attempts (11 successful payload calls + 17 retry attempts triggered by tenacity exponential backoff on HTTP 429 rate limits).
  * Wall time: 476.10 s (measured via `time.perf_counter()`). The 25 s sleep in `build.py` runs 5 times between the 6 outer 100-chunk slices (`125 s`), while tenacity exponential backoff delays across the 17 retries and network round-trip latency account for the remaining `351.1 s`.
  * File sizes:
    - `vectors.f16.npy`: 829.6 KB
    - `chunk_meta.jsonl`: 1527.0 KB
    - `bm25.json`: 1254.2 KB
    - `manifest.json`: 0.5 KB
  * Full `py tasks.py hash` output (Run 1):
    ```text
    089ac1f9f64a9bc4d42e04fa2ba33b349fcf8970398ef9a23efb5e9e4ec147bf  data/index/vectors.f16.npy
    8a00720b40d47caeae587a31cb3bb8da899159de7b17ad798e28337119ce61d1  data/index/bm25.json
    ```

- Run 2 (`py tasks.py index` - cached rerun):
  * Chunks indexed: 553
  * API calls made: 0 (all 553 chunk embeddings retrieved from `cache/embeddings`)
  * Wall time: 0.21 s
  * File sizes:
    - `vectors.f16.npy`: 829.6 KB
    - `chunk_meta.jsonl`: 1527.0 KB
    - `bm25.json`: 1254.2 KB
    - `manifest.json`: 0.5 KB
  * Full `py tasks.py hash` output (Run 2):
    ```text
    089ac1f9f64a9bc4d42e04fa2ba33b349fcf8970398ef9a23efb5e9e4ec147bf  data/index/vectors.f16.npy
    8a00720b40d47caeae587a31cb3bb8da899159de7b17ad798e28337119ce61d1  data/index/bm25.json
    ```
  * Hash comparison: Checksums are byte-identical across both runs.

3. Sanity-Check Results (`tools/index_sanity.py`, sample 100, seed 13):
- BM25 Top-1 Share: 0.99 (99/100, target > 0.85)
- Dense Top-10 Share: 0.98 (98/100, target > 0.60)
- Actual top-10 retrieval inspect for the 2 dense failures:
  * Target Row 37:
    - Target: Title='Memory', Heading path=['Manage short-term memory', 'Manage checkpoints'] (`add-memory.mdx#manage-checkpoints`)
    - Query text: `'Memory Manage short-term memory Manage checkpoints'`
    - Target Score: 0.7236 | Target Rank: **12** of 553
    - Actual Top-10 retrieved:
      1. Rank 1 (Row 33, Score 0.7536): Memory -> Manage short-term memory > Manage checkpoints (`add-memory.mdx#manage-checkpoints`)
      2. Rank 2 (Row 36, Score 0.7418): Memory -> Manage short-term memory > Manage checkpoints (`add-memory.mdx#manage-checkpoints`)
      3. Rank 3 (Row 8, Score 0.7407): Memory -> Add short-term memory > Use in production (`add-memory.mdx#use-in-production`)
      4. Rank 4 (Row 25, Score 0.7399): Memory -> Manage short-term memory (`add-memory.mdx#manage-short-term-memory`)
      5. Rank 5 (Row 34, Score 0.7365): Memory -> Manage short-term memory > Manage checkpoints (`add-memory.mdx#manage-checkpoints`)
      6. Rank 6 (Row 433, Score 0.7351): Use the functional API -> Short-term memory > Manage checkpoints (`use-functional-api.mdx#manage-checkpoints`)
      7. Rank 7 (Row 11, Score 0.7339): Memory -> Add short-term memory > Use in subgraphs (`add-memory.mdx#use-in-subgraphs`)
      8. Rank 8 (Row 1, Score 0.7320): Memory -> Add short-term memory > Use in production (`add-memory.mdx#use-in-production`)
      9. Rank 9 (Row 35, Score 0.7315): Memory -> Manage short-term memory > Manage checkpoints (`add-memory.mdx#manage-checkpoints`)
      10. Rank 10 (Row 0, Score 0.7296): Memory -> Add short-term memory (`add-memory.mdx#add-short-term-memory`)
    - Failure read: Row 37 is the 5th chunk of a multi-chunk documentation section (`Manage short-term memory > Manage checkpoints`). Sibling chunks from the identical section (Rows 33, 36, 34, 35) took ranks 1, 2, 5, and 9 with higher scores (0.7315–0.7536). The dense retriever correctly identified the exact documentation section, but sister chunks within the same section filled the top-10 slots.

  * Target Row 22:
    - Target: Title='Memory', Heading path=['Add long-term memory', 'Use in production'] (`add-memory.mdx#use-in-production-2`)
    - Query text: `'Memory Add long-term memory Use in production'`
    - Target Score: 0.7801 | Target Rank: **11** of 553
    - Actual Top-10 retrieved:
      1. Rank 1 (Row 1, Score 0.8066): Memory -> Add short-term memory > Use in production (`add-memory.mdx#use-in-production`)
      2. Rank 2 (Row 8, Score 0.8011): Memory -> Add short-term memory > Use in production (`add-memory.mdx#use-in-production`)
      3. Rank 3 (Row 14, Score 0.8002): Memory -> Add long-term memory > Use in production (`add-memory.mdx#use-in-production-2`)
      4. Rank 4 (Row 20, Score 0.7901): Memory -> Add long-term memory > Use in production (`add-memory.mdx#use-in-production-2`)
      5. Rank 5 (Row 16, Score 0.7875): Memory -> Add long-term memory > Use in production (`add-memory.mdx#use-in-production-2`)
      6. Rank 6 (Row 2, Score 0.7851): Memory -> Add short-term memory > Use in production (`add-memory.mdx#use-in-production`)
      7. Rank 7 (Row 12, Score 0.7842): Memory -> Add long-term memory (`add-memory.mdx#add-long-term-memory`)
      8. Rank 8 (Row 19, Score 0.7835): Memory -> Add long-term memory > Use in production (`add-memory.mdx#use-in-production-2`)
      9. Rank 9 (Row 9, Score 0.7830): Memory -> Add short-term memory > Use in production (`add-memory.mdx#use-in-production`)
      10. Rank 10 (Row 18, Score 0.7819): Memory -> Add long-term memory > Use in production (`add-memory.mdx#use-in-production-2`)
    - Failure read: Row 22 missed rank 10 by a score delta of 0.0018 (0.7801 vs 0.7819). Five sibling chunks from the identical section (`add-memory.mdx#use-in-production-2`, rows 14, 16, 18, 19, 20) took ranks 3, 4, 5, 8, and 10. Again, dense retrieval correctly localized the exact technical topic and page, but sibling chunks of the same multi-chunk section filled the top positions.

4. Bundle-Check Total:
- Total bundle size: 227.49 MB (limit: 400.00 MB)
- Increase of ~4.3 MB from M01 baseline (223.19 MB) due to committed index files (3.6 MB) and tenacity runtime dependency.

5. Acceptance Checks Summary:
| Check | Requirement | Result |
|---|---|---|
| Unit tests | `py tasks.py test` passes without network | PASS (55 passed in 1.14s) |
| Import boundaries | `ragdocs.api` never imports index.build or dev dependencies | PASS (verified in test_import_boundaries.py) |
| Live API test | `py tasks.py test-live` passes (shape 768, norm ~1.0) | PASS (1 passed in 1.37s) |
| Idempotent index rerun | 0 API calls, byte-identical hashes | PASS (0 API calls, 0.21s, identical SHA-256) |
| Sanity BM25 top-1 | > 0.85 | PASS (0.99) |
| Sanity dense top-10 | > 0.60 | PASS (0.98) |
| Bundle size | < 400 MB | PASS (227.49 MB) |
| Code quality | `py tasks.py lint` clean | PASS (68 files formatted) |

Decisions made
- D17 in docs/DECISIONS.md: Selected `gemini-embedding-001` at 768 dimensions with float16 numpy on-disk representation (`vectors.f16.npy`).
- Token-aware batching cap: Capped batches in `GeminiEmbedder` at 20,000 tokens (and 100 texts). Documentation chunks average 286.3 tokens; a naive 100-chunk batch totals ~32,500 tokens, which instantly exceeds the Google AI Studio free-tier 30,000 TPM limit in a single request and triggers unrecoverable 429 quota exhaustion.
- Rate-limit pacing: Added a 25 s pause between uncached outer slices in `build_index` to stay comfortably within the 30k TPM rolling window, completing full index construction in 7.9 minutes.

Deviations from the prompt
- Token-aware batching in addition to max batch size: While the prompt specified batching at the verified maximum (100), sending 100 full documentation chunks produces ~32,500 tokens, exceeding the free tier 30,000 TPM limit in a single request. `GeminiEmbedder` therefore batches by `min(100, texts_fitting_in_20k_tokens)`.
- Tenacity backoff parameter adjustment: Enhanced backoff logic to inspect API `RetryInfo` delay strings and apply a minimum 35 s backoff after multiple 429s, ensuring the rolling 1-minute window has reset before retrying.

Known issues and limitations
- Free-tier 1,000 requests-per-day item accounting: The Google AI Studio free tier limits requests to 100 RPM, 30,000 TPM, and 1,000 RPD (`EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier`). Per-item accounting is likely but unconfirmed (the 101-item error only proves the batch limit), and the 17 failed 429 attempts may also count toward RPD. Disk caching completely eliminates API consumption on repeated runs; for multiple full index rebuilds on fresh machines in a single day, wait for the daily reset or use a paid tier.
- Multi-chunk section disambiguation in dense retrieval: In 2 of 100 sampled sanity chunks (rows 37 and 22), the query matched the correct section anchor, but sibling chunks from the same multi-chunk section scored higher and filled the top-10 slots. Hybrid retrieval in M05 may help on real questions with body-specific terms, but heading-only queries like these cannot separate sibling chunks; evaluate on body-based queries in M05.

Open questions for the human
- None.

Proposed follow-ups (out of scope)
- [NOT DONE] Asynchronous batch API for large corpora: For future indexes with >10,000 chunks, integrate Google's asynchronous Cloud Storage batch API (`client.batches.create`) to bypass real-time TPM and RPM limits.

Prerequisites for the next module
- Hybrid retrieval index files committed in `data/index/` (`vectors.f16.npy`, `chunk_meta.jsonl`, `bm25.json`, `manifest.json`).
- `LoadedIndex` runtime loader verified and cached via `get_index()`.
- Human sets `COHERE_API_KEY` in `.env` for M05 reranker evaluation.
