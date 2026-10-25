"""Unit tests for RRF fusion, HybridRetriever modes, and LangChain DocsRetriever adapter."""

from typing import Any

import numpy as np

from ragdocs.config import Settings
from ragdocs.index.loader import LoadedIndex
from ragdocs.providers.reranker import NoopReranker, get_reranker
from ragdocs.retrieval.fusion import reciprocal_rank_fusion
from ragdocs.retrieval.langchain_adapter import DocsRetriever
from ragdocs.retrieval.retriever import HybridRetriever
from ragdocs.schemas import Chunk


def _make_dummy_chunk(row_idx: int) -> Chunk:
    """Create a dummy Chunk corresponding to a row index."""
    return Chunk(
        chunk_id=f"c_{row_idx:03d}",
        doc_path=f"docs/topic_{row_idx}.mdx",
        url=f"https://docs.langchain.com/docs/topic_{row_idx}#sec",
        title=f"Title {row_idx}",
        heading_path=[f"Section {row_idx}"],
        anchor="sec",
        text=f"Text content of chunk {row_idx}",
        embed_text=f"Title {row_idx} > Section {row_idx} > Text content {row_idx}",
        n_tokens=30,
        has_code=False,
        source_commit="commit123",
    )


class FakeVectorIndex:
    """Mock VectorIndex returning pre-configured results."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    def search(self, query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
        # Return row 0, 1, 2... with descending float scores
        return [(i, 1.0 - 0.1 * i) for i in range(min(k, len(self.chunks)))]

    def chunk(self, row: int) -> Chunk:
        return self.chunks[row]


class FakeBM25Index:
    """Mock BM25Index returning pre-configured results."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        # Return row 2, 1, 0, 3... with descending BM25 scores
        order = [2, 1, 0, 3, 4]
        return [(idx, 10.0 - 1.0 * i) for i, idx in enumerate(order) if idx < len(self.chunks)][:k]


class FakeEmbedder:
    """Mock Embedder returning fixed query embedding."""

    def embed_query(self, text: str) -> np.ndarray:
        return np.ones((768,), dtype=np.float32)


class FakeReranker:
    """Mock Reranker inverting order to test reranking effect."""

    def rerank(self, query: str, texts: list[str], top_n: int) -> list[tuple[int, float]]:
        # Invert order: last candidate text becomes first
        n = min(top_n, len(texts))
        return [(len(texts) - 1 - i, 0.95 - 0.05 * i) for i in range(n)]


def test_reciprocal_rank_fusion_hand_example_and_ties() -> None:
    """Test RRF on a hand-calculated example with intentional score ties.

    Ranking 1: [1, 2, 3]
    Ranking 2: [2, 1, 4]
    With k = 60:
    row 1: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.03252248...
    row 2: 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.03252248... (TIE with row 1)
    row 3: 1/(60+3) = 1/63 = 0.01587301...
    row 4: 1/(60+3) = 1/63 = 0.01587301... (TIE with row 3)

    Determinism requirement: ties broken by lower row index.
    Expected order: row 1, then row 2, then row 3, then row 4.
    """
    rankings = [
        [1, 2, 3],
        [2, 1, 4],
    ]
    fused = reciprocal_rank_fusion(rankings, k=60)
    assert len(fused) == 4

    rows = [row for row, _ in fused]
    assert rows == [1, 2, 3, 4]

    # Check scores
    score_1 = fused[0][1]
    score_2 = fused[1][1]
    assert abs(score_1 - score_2) < 1e-9
    assert abs(score_1 - (1.0 / 61.0 + 1.0 / 62.0)) < 1e-9

    score_3 = fused[2][1]
    score_4 = fused[3][1]
    assert abs(score_3 - score_4) < 1e-9
    assert abs(score_3 - 1.0 / 63.0) < 1e-9


def test_reciprocal_rank_fusion_empty() -> None:
    """Test RRF handles empty ranking lists."""
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_noop_reranker() -> None:
    """Test NoopReranker preserves candidate order with 0.0 scores."""
    noop = NoopReranker()
    texts = ["doc a", "doc b", "doc c"]
    res = noop.rerank("query", texts, top_n=2)
    assert res == [(0, 0.0), (1, 0.0)]

    assert noop.rerank("query", [], top_n=5) == []
    assert noop.rerank("query", texts, top_n=0) == []


def test_get_reranker_noop_when_disabled() -> None:
    """Test get_reranker returns NoopReranker when use_reranker is False."""
    settings = Settings(use_reranker=False)
    reranker = get_reranker(settings)
    assert isinstance(reranker, NoopReranker)


def test_hybrid_retriever_all_modes() -> None:
    """Test HybridRetriever across dense, bm25, hybrid, and hybrid_rerank modes."""
    chunks = [_make_dummy_chunk(i) for i in range(10)]
    vec_index = FakeVectorIndex(chunks)
    bm25_index = FakeBM25Index(chunks)
    loaded_index = LoadedIndex(
        vector_index=vec_index,  # type: ignore[arg-type]
        bm25_index=bm25_index,  # type: ignore[arg-type]
        manifest={"n_chunks": 10},
    )
    embedder = FakeEmbedder()
    reranker = FakeReranker()
    settings = Settings(
        dense_k=5,
        bm25_k=5,
        rrf_k=60,
        fused_k=4,
        rerank_top_n=3,
        final_k=3,
    )

    retriever = HybridRetriever(
        index=loaded_index,
        embedder=embedder,
        reranker=reranker,
        settings=settings,
    )

    # 1. Candidate diagnostic method
    candidates = retriever.retrieve_candidates("test query")
    assert len(candidates) == 4
    assert [c.rank for c in candidates] == [1, 2, 3, 4]
    assert all(c.retriever == "hybrid" for c in candidates)

    # 2. Dense mode
    dense_chunks = retriever.retrieve("test query", mode="dense")
    assert len(dense_chunks) == 3
    assert [c.rank for c in dense_chunks] == [1, 2, 3]
    assert all(c.retriever == "dense" for c in dense_chunks)
    assert [c.chunk.chunk_id for c in dense_chunks] == ["c_000", "c_001", "c_002"]

    # 3. BM25 mode
    bm25_chunks = retriever.retrieve("test query", mode="bm25")
    assert len(bm25_chunks) == 3
    assert [c.rank for c in bm25_chunks] == [1, 2, 3]
    assert all(c.retriever == "bm25" for c in bm25_chunks)
    assert [c.chunk.chunk_id for c in bm25_chunks] == ["c_002", "c_001", "c_000"]

    # 4. Hybrid mode
    hybrid_chunks = retriever.retrieve("test query", mode="hybrid")
    assert len(hybrid_chunks) == 3
    assert [c.rank for c in hybrid_chunks] == [1, 2, 3]
    assert all(c.retriever == "hybrid" for c in hybrid_chunks)

    # 5. Hybrid rerank mode
    reranked_chunks = retriever.retrieve("test query", mode="hybrid_rerank")
    assert len(reranked_chunks) == 3
    assert [c.rank for c in reranked_chunks] == [1, 2, 3]
    assert all(c.retriever == "hybrid_rerank" for c in reranked_chunks)
    # FakeReranker inverts the candidate list: candidate 3 becomes top
    assert reranked_chunks[0].chunk.chunk_id == candidates[3].chunk.chunk_id


def test_langchain_adapter_docs_retriever() -> None:
    """Test DocsRetriever wraps HybridRetriever and returns Document with all metadata keys."""
    chunks = [_make_dummy_chunk(i) for i in range(5)]
    vec_index = FakeVectorIndex(chunks)
    bm25_index = FakeBM25Index(chunks)
    loaded_index = LoadedIndex(
        vector_index=vec_index,  # type: ignore[arg-type]
        bm25_index=bm25_index,  # type: ignore[arg-type]
        manifest={"n_chunks": 5},
    )
    embedder = FakeEmbedder()
    reranker = FakeReranker()
    settings = Settings(final_k=2, rerank_top_n=2)
    hybrid_retriever = HybridRetriever(
        index=loaded_index,
        embedder=embedder,
        reranker=reranker,
        settings=settings,
    )

    docs_retriever = DocsRetriever(retriever=hybrid_retriever, mode="dense")
    docs = docs_retriever.invoke("test question")

    assert len(docs) == 2
    for doc in docs:
        assert isinstance(doc.page_content, str)
        assert len(doc.page_content) > 0
        metadata: dict[str, Any] = doc.metadata
        for required_key in ["chunk_id", "url", "title", "heading_path", "score", "rank"]:
            assert required_key in metadata, f"Missing required metadata key: {required_key}"
