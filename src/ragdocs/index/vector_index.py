"""Dense vector index with numpy dot product search."""

from pathlib import Path
from typing import Self

import numpy as np

from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import Chunk


class VectorIndex:
    """In-memory vector index searching normalized float32 embeddings with numpy."""

    def __init__(self, vectors: np.ndarray, chunks: list[Chunk]) -> None:
        self.vectors = vectors
        self.chunks = chunks

    @classmethod
    def load(cls, index_dir: Path | str) -> Self:
        """Load vectors.f16.npy as float32 and chunk_meta.jsonl as list[Chunk]."""
        p = Path(index_dir)
        vec_path = p / "vectors.f16.npy"
        meta_path = p / "chunk_meta.jsonl"

        vectors = np.load(vec_path).astype(np.float32)
        raw_chunks = read_jsonl(meta_path)
        chunks = [Chunk.model_validate(c) for c in raw_chunks]
        return cls(vectors=vectors, chunks=chunks)

    def search(self, query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Search top-k nearest vectors by dot product, returning (row, score) sorted descending."""
        if len(self.vectors) == 0 or k <= 0:
            return []

        scores = np.dot(self.vectors, query_vec.astype(np.float32))
        top_k = min(k, len(scores))
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(int(idx), float(scores[idx])) for idx in top_indices]

    def chunk(self, row: int) -> Chunk:
        """Return the chunk metadata at the specified row index."""
        return self.chunks[row]
