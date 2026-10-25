M05: Hybrid retrieval and reranking
Status: Done
Date: 2026-10-25

Goal
Build a runtime-safe HybridRetriever supporting dense, BM25, RRF hybrid, and Cohere reranking modes; provide a LangChain BaseRetriever adapter (DocsRetriever); implement offline retrieval metrics (Hit@k, MRR, Evidence Recall@k); execute a committed ablation run across all 42 answerable benchmark questions with disk caching; and evaluate the Decision D6 gate for production reranking.

What was built
- src/ragdocs/config.py: Set Settings.rerank_model default to verified "rerank-v3.5", added use_reranker defaulting to False (after D6 gate).
- src/ragdocs/retrieval/fusion.py: Implemented reciprocal_rank_fusion with 1-based ranks and deterministic lower-row tie-breaking.
- src/ragdocs/providers/reranker.py: Implemented Reranker Protocol, NoopReranker, CohereReranker with tenacity retry (429/5xx), and get_reranker factory.
- src/ragdocs/retrieval/retriever.py: Implemented HybridRetriever with dense, bm25, hybrid, and hybrid_rerank modes and retrieve_candidates diagnostic method.
- src/ragdocs/retrieval/langchain_adapter.py: Implemented DocsRetriever wrapping HybridRetriever for LangChain BaseRetriever compatibility.
- src/ragdocs/eval/metrics.py: Implemented offline metrics (matches, hit_at_k, mrr, evidence_recall_at_k).
- scripts/eval_retrieval.py: CLI script evaluating retrieval accuracy across 42 answerable items with diskcache query/rerank caching and markdown tables.
- tests/test_metrics.py: Unit tests for retrieval metrics edge cases (empty lists, negative k, multiple evidence, absent evidence).
- tests/test_retrieval.py: Unit tests for RRF with hand-crafted ties, HybridRetriever modes with mocks, NoopReranker, and DocsRetriever metadata keys.
- results/runs/retrieval-20261025/config.json: Benchmark execution metadata, Settings values, manifest hash, and commit hash.
- results/runs/retrieval-20261025/per_question.jsonl: Detailed per-question retrieval outputs, scores, and metrics across all 4 modes.
- results/runs/retrieval-20261025/table.md: Formatted markdown summary tables with overall and per-category retrieval metrics.
- docs/DECISIONS.md: Recorded D6 gate decision (FAIL, gain = 1 < 3, use_reranker = False).
- docs/progress/PROGRESS.md: Updated M05 row status to Done with date and tracking file link.
- docs/progress/M05-retrieval.md: Progress tracking document for module M05.

How to run
- Run retrieval evaluation: `.venv\Scripts\python scripts/eval_retrieval.py`
- Run unit test suite: `py tasks.py test`
- Run linter and formatter: `py tasks.py lint`

Verification
1. Step 1 Verification Table (API & SDK Findings):
| Item | Verified Value | Source URL / Installed SDK File Path |
|---|---|---|
| Current Cohere rerank model ID | `rerank-v3.5` | `https://docs.cohere.com/v2/docs/rerank`<br>`.venv/Lib/site-packages/cohere/v2/client.py` (explicit docstring example: `model: The identifier of the model to use, eg rerank-v3.5`) |
| ClientV2 rerank call signature | `client.rerank(model: str, query: str, documents: Sequence[str], top_n: Optional[int] = ..., max_tokens_per_doc: Optional[int] = ..., priority: Optional[int] = ..., request_options: Optional[RequestOptions] = None) -> V2RerankResponse` | `.venv/Lib/site-packages/cohere/v2/client.py`<br>`https://docs.cohere.com/v2/reference/rerank` |
| Trial-key rate limit | 10 requests per minute (RPM), 1,000 requests per month | `https://docs.cohere.com/v2/docs/rate-limits` |
| Maximum documents per request | Up to 10,000 documents per call (recommendation: under 1,000 for latency/performance) | `https://docs.cohere.com/v2/reference/rerank` |
| BaseRetriever method to override | `_get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None, **kwargs: Any) -> list[Document]` | `.venv/Lib/site-packages/langchain_core/retrievers.py` |

2. Retrieval Ablation Results (`results/runs/retrieval-20261025/table.md`):

### Overall Retrieval Performance (N=42 Answerable Questions)

| Mode | Hit@1 | Hit@5 | MRR | Evidence Recall@5 |
|---|---|---|---|---|
| `dense` | 0.524 (22/42) | 0.833 (35/42) | 0.640 (26.9/42) | 0.750 (31.5/42) |
| `bm25` | 0.262 (11/42) | 0.595 (25/42) | 0.366 (15.4/42) | 0.536 (22.5/42) |
| `hybrid` | 0.524 (22/42) | 0.810 (34/42) | 0.631 (26.5/42) | 0.726 (30.5/42) |
| `hybrid_rerank` | 0.405 (17/42) | 0.833 (35/42) | 0.575 (24.1/42) | 0.738 (31/42) |

*Diagnostic Candidate Pool Recall: `retrieve_candidates` Hit@20 = 0.929 (39/42)*

### Retrieval Performance Broken Down by Category

| Category | Mode | Hit@1 | Hit@5 | MRR | Evidence Recall@5 |
|---|---|---|---|---|---|
| single (N=28) | `dense` | 0.536 (15/28) | 0.821 (23/28) | 0.664 (18.6/28) | 0.821 (23/28) |
| single (N=28) | `bm25` | 0.286 (8/28) | 0.571 (16/28) | 0.382 (10.7/28) | 0.571 (16/28) |
| single (N=28) | `hybrid` | 0.536 (15/28) | 0.786 (22/28) | 0.643 (18/28) | 0.786 (22/28) |
| single (N=28) | `hybrid_rerank` | 0.429 (12/28) | 0.786 (22/28) | 0.567 (15.9/28) | 0.786 (22/28) |
| multi (N=8) | `dense` | 0.500 (4/8) | 0.750 (6/8) | 0.550 (4.4/8) | 0.375 (3/8) |
| multi (N=8) | `bm25` | 0.125 (1/8) | 0.625 (5/8) | 0.269 (2.1/8) | 0.375 (3/8) |
| multi (N=8) | `hybrid` | 0.500 (4/8) | 0.875 (7/8) | 0.625 (5/8) | 0.500 (4/8) |
| multi (N=8) | `hybrid_rerank` | 0.375 (3/8) | 0.875 (7/8) | 0.567 (4.5/8) | 0.438 (3.5/8) |
| version (N=6) | `dense` | 0.500 (3/6) | 1.000 (6/6) | 0.650 (3.9/6) | 0.917 (5.5/6) |
| version (N=6) | `bm25` | 0.333 (2/6) | 0.667 (4/6) | 0.422 (2.5/6) | 0.583 (3.5/6) |
| version (N=6) | `hybrid` | 0.500 (3/6) | 0.833 (5/6) | 0.583 (3.5/6) | 0.750 (4.5/6) |
| version (N=6) | `hybrid_rerank` | 0.333 (2/6) | 1.000 (6/6) | 0.625 (3.8/6) | 0.917 (5.5/6) |

3. D6 Gate Outcome:
- `hybrid` Hit@5 count: 34 / 42 (81.0%)
- `hybrid_rerank` Hit@5 count: 35 / 42 (83.3%)
- Net Hit@5 gain: 1 question (35 - 34 = 1).
- Decision threshold: gain >= 3 questions.
- Result: FAIL (gain = 1 < 3).
- Action taken: `Settings.use_reranker` default set to `False` in `src/ragdocs/config.py`. Recorded under D6 in `docs/DECISIONS.md`.

4. Zero API Calls Verification on Cached Rerun:
- Command: `.venv\Scripts\python scripts/eval_retrieval.py`
- API calls made: `embeddings=0`, `rerank=0`
- Execution speed: 256.14 it/s (0.16 s total execution time)
- Output tables: 100% byte-identical reproduction.

5. Questions Unretrieved Across All Modes (Hit@5 == 0):
Exactly 4 answerable questions failed to be retrieved within top-5 across all 4 modes (`dense`, `bm25`, `hybrid`, `hybrid_rerank`):

1. `q008` (category: `single`)
   - Question: "How can I retrieve the complete sequence of past checkpoints recorded for a specific conversation?"
   - Gold Evidence: `checkpointers.mdx#get-state-history`
   - Retrieved Candidate Pool Rank: 14 (in top-20 candidate pool, but outside top-5).
   - Top 3 Retrieved Headings (`hybrid_rerank`):
     1. Use the functional API > Short-term memory > Manage checkpoints (`use-functional-api.mdx#manage-checkpoints`)
     2. Memory > Manage short-term memory (`add-memory.mdx#manage-short-term-memory`)
     3. Memory > Manage short-term memory > Manage checkpoints (`add-memory.mdx#manage-checkpoints`)
   - Note: Dense search favoured functional API and general memory checkpoint guides over the low-level `checkpointers.mdx#get-state-history` reference chunk.

2. `q012` (category: `single`)
   - Question: "Which built-in state class gives me a messages list out of the box?"
   - Gold Evidence: `agentic-rag.mdx#generate-a-query-or-respond`
   - Top 3 Retrieved Headings (`hybrid_rerank`):
     1. Use the graph API > Define and update state > Define state (`use-graph-api.mdx#define-state`)
     2. Graph API overview > State > Working with messages in graph state (`graph-api.mdx#working-with-messages-in-graph-state`)
     3. Graph API overview > State > Working with messages in graph state (`graph-api.mdx#working-with-messages-in-graph-state-2`)
   - Note: The question asks about `MessagesState`. Dense and BM25 matched general state definition and "working with messages in graph state" rather than the tutorial notebook anchor in `agentic-rag.mdx`.

3. `q018` (category: `single`)
   - Question: "How can I stream model output as individual tokens from my graph?"
   - Gold Evidence: `streaming.mdx#stream-modes`
   - Top 3 Retrieved Headings (`hybrid_rerank`):
     1. Streaming > Stream modes > LLM tokens (`streaming.mdx#llm-tokens`)
     2. Streaming > Stream modes > LLM tokens (`streaming.mdx#llm-tokens-2`)
     3. Streaming > Advanced > Use with any LLM (`streaming.mdx#use-with-any-llm`)
   - Note: Gold evidence specified the parent section anchor (`#stream-modes`), but the retriever retrieved the exact token streaming child subheadings (`#llm-tokens`, `#llm-tokens-2`). Technically relevant content was localized, but missed exact anchor equality.

4. `q039` (category: `single`)
   - Question: "How can a node dynamically decide which destination node to trigger next while updating state?"
   - Gold Evidence: `thinking-in-langgraph.mdx#handle-errors-appropriately`
   - Top 3 Retrieved Headings (`hybrid_rerank`):
     1. Use the graph API > Combine control flow and state updates with Command (`use-graph-api.mdx#combine-control-flow-and-state-updates-with-command`)
     2. Use the graph API > Create branches > Conditional branching (`use-graph-api.mdx#conditional-branching`)
     3. Graph API overview > Command > Return from nodes (`graph-api.mdx#return-from-nodes`)
   - Note: The question describes the core functionality of `Command`. The retriever returned the authoritative `use-graph-api.mdx` and `graph-api.mdx` sections on `Command`, whereas the gold benchmark evidence points to an illustrative example in `thinking-in-langgraph.mdx#handle-errors-appropriately`.

6. Code Quality & Test Suite:
- `py tasks.py lint`: PASS (77 files cleanly formatted).
- `py tasks.py test`: PASS (66 passed, 1 deselected in 1.28 s).
- Import boundaries verified: `ragdocs.api` never touches `ragdocs.eval` or `ragdocs.ingest`.

Decisions made
- D6 Gate Decision: Cohere Rerank disabled in production (`use_reranker = False` in `src/ragdocs/config.py`).
  - Reason: `hybrid_rerank` achieved Hit@5 of 35/42 vs `hybrid` at 34/42, yielding a gain of only 1 question (threshold: >= 3). Moreover, Cohere reranking noticeably degraded top-1 precision (Hit@1 dropped from 22/42 to 17/42, and MRR dropped from 0.631 to 0.575), while adding latency and external API dependency.
- Throttling & Caching: Embedded query caching in `cache/embeddings` and reranking responses in `cache/rerank` using `diskcache`. Uncached Cohere calls are throttled at 6.2 s intervals to strictly respect the 10 RPM trial rate limit.

Deviations from the prompt
- None. All implementation constraints and interfaces followed precisely.

Known issues and limitations
- Cohere Rerank degradation at rank 1: Cross-encoder reranking on `embed_text` with `rerank-v3.5` demoted several top-1 hits from dense search, dropping overall Hit@1 by 11.9% (22 -> 17). Dense embeddings alone provided higher reciprocal rank (MRR 0.640 vs 0.575).
- Anchor mismatch on parent vs child sections: As observed in `q018`, documentation chunking splits child sections into separate chunks. When an eval item lists a parent overview anchor as gold evidence, retrieval targeting specific child subheadings fails the strict `(doc_path, anchor)` equality test.

Open questions for the human
- None.

Proposed follow-ups (out of scope)
- [NOT DONE] Hierarchical / parent-child anchor matching: In future eval metric iterations, consider allowing child chunk matches when the gold evidence specifies an immediately enclosing parent anchor on the same page.
- [NOT DONE] Query expansion / HyDE: Experiment with hypothetical document embeddings (HyDE) in offline experiments to see if technical terms like `MessagesState` (q012) can be bridged.

Prerequisites for the next module
- HybridRetriever and LangChain DocsRetriever adapter verified.
- Settings.use_reranker set to False.
- Frozen eval set and evaluation cache available for baseline generation (M06).
