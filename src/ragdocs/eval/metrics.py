"""Offline retrieval evaluation metrics."""

from collections.abc import Sequence
from typing import Any

from ragdocs.schemas import Chunk, Evidence, RetrievedChunk


def matches(chunk: Chunk | RetrievedChunk | Any, evidence: Evidence) -> bool:
    """Return True when chunk doc_path and anchor match evidence doc_path and anchor."""
    c = chunk.chunk if isinstance(chunk, RetrievedChunk) else chunk
    return bool(c.doc_path == evidence.doc_path and c.anchor == evidence.anchor)


def hit_at_k(
    retrieved: Sequence[RetrievedChunk | Chunk | Any],
    evidence: Sequence[Evidence],
    k: int,
) -> float:
    """Return 1.0 if any top-k retrieved chunk matches any evidence entry, else 0.0."""
    if not evidence or not retrieved or k <= 0:
        return 0.0

    top_k = retrieved[:k]
    for item in top_k:
        for ev in evidence:
            if matches(item, ev):
                return 1.0
    return 0.0


def mrr(
    retrieved: Sequence[RetrievedChunk | Chunk | Any],
    evidence: Sequence[Evidence],
) -> float:
    """Return the reciprocal rank (1/rank) of the first matching chunk, or 0.0 if absent."""
    if not evidence or not retrieved:
        return 0.0

    for idx, item in enumerate(retrieved):
        rank = idx + 1
        for ev in evidence:
            if matches(item, ev):
                return 1.0 / rank
    return 0.0


def evidence_recall_at_k(
    retrieved: Sequence[RetrievedChunk | Chunk | Any],
    evidence: Sequence[Evidence],
    k: int,
) -> float:
    """Return share of evidence entries matched by at least one of the top k retrieved chunks."""
    if not evidence:
        return 0.0
    if not retrieved or k <= 0:
        return 0.0

    top_k = retrieved[:k]
    matched_count = 0
    for ev in evidence:
        if any(matches(item, ev) for item in top_k):
            matched_count += 1

    return matched_count / len(evidence)
