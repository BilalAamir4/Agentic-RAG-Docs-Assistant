M04: Index build
Status: Done
Date: 2026-10-22

Goal
Build dense vector and sparse BM25 retrieval indexes over data/processed/chunks.jsonl offline with disk caching, commit them to data/index/, provide runtime search interfaces without torch or vector database dependencies, and verify retrieval accuracy with sanity checks.

What was built
- src/ragdocs/config.py: Set Settings.embedding_model default to verified "gemini-embedding-001".
- requirements.txt: Moved tenacity==9.1.4 into runtime dependencies.
- requirements-dev.txt: Removed tenacity==9.1.4.
- src/ragdocs/providers/embeddings.py: Runtime-safe GeminiEmbedder with batching, exponential backoff on 429/5xx, and L2 normalization.
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

How to run
- Build index: `py tasks.py index`
- Run unit test suite: `py tasks.py test`
- Run live embeddings test: `py tasks.py test-live`
- Run linter and formatter: `py tasks.py lint`
- Compute index checksums: `py tasks.py hash data/index/vectors.f16.npy data/index/bm25.json`
- Run retrieval sanity check: `.venv\Scripts\python tools/index_sanity.py`
- Check deployment bundle size: `py tasks.py bundle-check`

Verification
1. Step 1 API Verification:
   - Current stable embedding model ID: `gemini-embedding-001` (text-embedding-004 was shut down as of 2026-01-14 and returns 404 NOT_FOUND).
   - How to request 768-dim output: `types.EmbedContentConfig(output_dimensionality=768, task_type=...)`.
   - Task types: `RETRIEVAL_DOCUMENT` for document chunks, `RETRIEVAL_QUERY` for queries.
   - Batch size and token limits: Maximum 100 requests per payload (`BatchEmbedContentsRequest.requests: at most 100 requests can be in one batch`); max input length 2,048 tokens per text.
   - Truncated dimension normalization: Raw output norm for 768-dim vectors from `gemini-embedding-001` is ~0.587–0.595; vectors must be L2-normalised by the caller (`vec / np.linalg.norm(vec)`).
   - Free tier rate limits: 100 RPM, 30,000 TPM, 1,000 RPD.
   - Sources checked:
     - `https://ai.google.dev/gemini-api/docs/embeddings`
     - `https://ai.google.dev/gemini-api/docs/rate-limits`
     - Installed package source: `.venv/Lib/site-packages/google/genai/models.py`, `types.py`, and `_api_client.py`.

2. Index Build Run 1 (`py tasks.py index`):
```text
=== Index Build Report ===
Chunks indexed: 553
API calls made: 28
Wall time: 476.10 s
Generated files:
  - vectors.f16.npy (829.6 KB): sha256=089ac1f9f64a9bc4d42e04fa2ba33b349fcf8970398ef9a23efb5e9e4ec147bf
  - chunk_meta.jsonl (1527.0 KB): sha256=f3614b3f74d9f5ff1a4213937132e9928e7b1904992fbee36092be3bbe046bc5
  - bm25.json (1254.2 KB): sha256=8a00720b40d47caeae587a31cb3bb8da899159de7b17ad798e28337119ce61d1
Manifest written to: C:\Users\Bilal Aamir\Documents\GitHub\RAG Docs Assistant\data\index\manifest.json
==========================
```

3. Index Build Run 2 (`py tasks.py index` - cache verification):
```text
=== Index Build Report ===
Chunks indexed: 553
API calls made: 0
Wall time: 0.21 s
Generated files:
  - vectors.f16.npy (829.6 KB): sha256=089ac1f9f64a9bc4d42e04fa2ba33b349fcf8970398ef9a23efb5e9e4ec147bf
  - chunk_meta.jsonl (1527.0 KB): sha256=f3614b3f74d9f5ff1a4213937132e9928e7b1904992fbee36092be3bbe046bc5
  - bm25.json (1254.2 KB): sha256=8a00720b40d47caeae587a31cb3bb8da899159de7b17ad798e28337119ce61d1
Manifest written to: C:\Users\Bilal Aamir\Documents\GitHub\RAG Docs Assistant\data\index\manifest.json
==========================
```

4. Checksums (`py tasks.py hash data/index/vectors.f16.npy data/index/bm25.json`):
```text
089ac1f9f64a9bc4d42e04fa2ba33b349fcf8970398ef9a23efb5e9e4ec147bf  data/index/vectors.f16.npy
8a00720b40d47caeae587a31cb3bb8da899159de7b17ad798e28337119ce61d1  data/index/bm25.json
```

5. Sanity Checks (`tools/index_sanity.py`, sample 100, seed 13):
```text
=== Running Index Retrieval Sanity Checks ===
Corpus size: 553 chunks | Sampled: 100 chunks (seed=13)

1. BM25 Sparse Check (Query: 5 rarest tokens by document frequency)...
   BM25 Top-1 share: 0.99 (99/100)

2. Dense Vector Check (Query: title + heading_path)...
   Dense Top-10 share: 0.98 (98/100)

=== Sanity Check Summary ===
BM25 Top-1 Share:  0.99 (Target > 0.85)
Dense Top-10 Share: 0.98 (Target > 0.60)
============================
```
- Dense top-10 failure cases (2 total out of 100):
  1. Chunk row 37: title='Memory', heading_path=['Manage short-term memory', 'Manage checkpoints']
  2. Chunk row 22: title='Memory', heading_path=['Add long-term memory', 'Use in production']

6. Bundle Size Check (`py tasks.py bundle-check`):
```text
Total bundle size: 227.49 MB (limit: 400.00 MB)
```

7. Unit Tests (`py tasks.py test`):
```text
.......................................................                  [100%]
55 passed, 1 deselected in 1.23s
```

8. Live Integration Test (`py tasks.py test-live`):
```text
.                                                                        [100%]
1 passed, 55 deselected in 1.37s
```

9. Code Quality & Linter (`py tasks.py lint`):
```text
All checks passed!
67 files already formatted
Running ruff check...
Running ruff format --check...
```

Decisions made
- Embedding model selection: Selected `gemini-embedding-001` as the default embedding model (`Settings.embedding_model = "gemini-embedding-001"`). Google retired `text-embedding-004` on 2026-01-14; `gemini-embedding-001` is the current stable production text embedding model supporting Matryoshka dimensionality reduction down to 768. (Appended as D17 in docs/DECISIONS.md)
- Rate-limit pacing and token-aware batching: On free tier, Gemini embeddings enforce a 30,000 TPM limit alongside 100 RPM. A full batch of 100 documentation chunks exceeds 32,000 tokens in a single request, triggering immediate quota rejection. `GeminiEmbedder` batches texts up to 100 items AND caps estimated batch tokens at 20,000, and `build_index` pauses between uncached batches to stay comfortably within the 30k TPM window.
- Float16 vector representation: Saved dense embedding vectors as float16 (`vectors.f16.npy`), requiring only 829.6 KB for 553 768-dimensional chunks while loading into float32 for exact dot product computation at runtime.

Deviations from the prompt
- None. All components specified in Step 1, Step 2, and Step 3 were implemented, tested, and verified.

Known issues and limitations
- Free tier quota limits: The Google AI Studio free tier limits requests to 100 RPM, 30,000 TPM, and 1,000 RPD. While disk caching eliminates all API calls on repeated index builds, building an index from scratch on a completely empty cache takes ~7-8 minutes due to token rate-limit pauses.
- Two generic heading query failures in dense retrieval: In 2 of 100 sampled sanity chunks, generic section headings ("Memory" with sub-sections) clustered closely with adjacent subsections, ranking outside the top-10 for the exact chunk while still matching the broader section topic.

Open questions for the human
- None.

Proposed follow-ups (out of scope)
- [NOT DONE] Batch API integration: For large multi-thousand chunk corpora in future projects, integrate Google's asynchronous Cloud Storage batch embedding API (`client.batches.create`) to bypass real-time TPM caps.

Prerequisites for the next module
- Hybrid retrieval index files committed in `data/index/` (`vectors.f16.npy`, `chunk_meta.jsonl`, `bm25.json`, `manifest.json`).
- `LoadedIndex` runtime loader verified and cached via `get_index()`.
- Human sets `COHERE_API_KEY` in `.env` if reranking is evaluated in M05.
