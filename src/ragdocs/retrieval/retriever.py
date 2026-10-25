"""Hybrid retriever combining dense semantic search, BM25 sparse search, and reranking."""

from functools import lru_cache
from typing import Any, Literal

from ragdocs.config import Settings, get_settings
from ragdocs.index.loader import LoadedIndex, get_index
from ragdocs.providers.reranker import Reranker
from ragdocs.retrieval.fusion import reciprocal_rank_fusion
from ragdocs.schemas import RetrievedChunk

RetrievalMode = Literal["dense", "bm25", "hybrid", "hybrid_rerank"]


class HybridRetriever:
    """Retriever supporting dense, BM25, RRF hybrid, and Cohere reranking modes."""

    def __init__(
        self,
        index: LoadedIndex,
        embedder: Any,
        reranker: Reranker,
        settings: Settings | None = None,
    ) -> None:
        self.index = index
        self.embedder = embedder
        self.reranker = reranker
        self.settings = settings or get_settings()

    def retrieve_candidates(self, query: str) -> list[RetrievedChunk]:
        """Retrieve fused candidate chunks prior to reranking for diagnostics.

        Executes dense search (top dense_k) and BM25 search (top bm25_k),
        combines them via RRF with rrf_k, and returns the top fused_k chunks.

        Args:
            query: User query string.

        Returns:
            List of fused RetrievedChunk instances of length up to fused_k.
        """
        query_vec = self.embedder.embed_query(query)
        dense_results = self.index.vector_index.search(query_vec, k=self.settings.dense_k)
        bm25_results = self.index.bm25_index.search(query, k=self.settings.bm25_k)

        dense_rows = [row for row, _ in dense_results]
        bm25_rows = [row for row, _ in bm25_results]

        fused = reciprocal_rank_fusion([dense_rows, bm25_rows], k=self.settings.rrf_k)
        fused = fused[: self.settings.fused_k]

        candidates: list[RetrievedChunk] = []
        for idx, (row, score) in enumerate(fused):
            chunk = self.index.vector_index.chunk(row)
            candidates.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=score,
                    rank=idx + 1,
                    retriever="hybrid",
                )
            )
        return candidates

    def retrieve(
        self,
        query: str,
        mode: RetrievalMode | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve top chunks for query according to the specified mode.

        Args:
            query: User query string.
            mode: Retrieval pipeline mode ('dense', 'bm25', 'hybrid', 'hybrid_rerank').
                Defaults to 'hybrid_rerank' if use_reranker is True, else 'hybrid'.

        Returns:
            List of RetrievedChunk instances up to final_k in length with 1-based ranks.
        """
        if mode is None:
            mode = "hybrid_rerank" if self.settings.use_reranker else "hybrid"
        if mode == "dense":
            query_vec = self.embedder.embed_query(query)
            dense_results = self.index.vector_index.search(query_vec, k=self.settings.dense_k)
            dense_cut = dense_results[: self.settings.final_k]
            return [
                RetrievedChunk(
                    chunk=self.index.vector_index.chunk(row),
                    score=score,
                    rank=idx + 1,
                    retriever="dense",
                )
                for idx, (row, score) in enumerate(dense_cut)
            ]

        if mode == "bm25":
            bm25_results = self.index.bm25_index.search(query, k=self.settings.bm25_k)
            bm25_cut = bm25_results[: self.settings.final_k]
            return [
                RetrievedChunk(
                    chunk=self.index.vector_index.chunk(row),
                    score=score,
                    rank=idx + 1,
                    retriever="bm25",
                )
                for idx, (row, score) in enumerate(bm25_cut)
            ]

        if mode == "hybrid":
            candidates = self.retrieve_candidates(query)
            hybrid_cut = candidates[: self.settings.final_k]
            return [
                RetrievedChunk(
                    chunk=c.chunk,
                    score=c.score,
                    rank=idx + 1,
                    retriever="hybrid",
                )
                for idx, c in enumerate(hybrid_cut)
            ]

        if mode == "hybrid_rerank":
            candidates = self.retrieve_candidates(query)
            if not candidates:
                return []
            texts = [c.chunk.embed_text for c in candidates]
            rerank_results = self.reranker.rerank(
                query=query,
                texts=texts,
                top_n=self.settings.rerank_top_n,
            )
            rerank_cut = rerank_results[: self.settings.final_k]
            return [
                RetrievedChunk(
                    chunk=candidates[input_idx].chunk,
                    score=score,
                    rank=idx + 1,
                    retriever="hybrid_rerank",
                )
                for idx, (input_idx, score) in enumerate(rerank_cut)
            ]

        raise ValueError(f"Unknown retrieval mode: {mode}")


@lru_cache
def get_retriever(settings: Settings | None = None) -> HybridRetriever:
    """Return cached HybridRetriever initialized from default settings and index."""
    s = settings or get_settings()
    index = get_index()
    from ragdocs.providers.embeddings import GeminiEmbedder
    from ragdocs.providers.reranker import get_reranker

    embedder = GeminiEmbedder(s)
    reranker = get_reranker(s)
    return HybridRetriever(
        index=index,
        embedder=embedder,
        reranker=reranker,
        settings=s,
    )
