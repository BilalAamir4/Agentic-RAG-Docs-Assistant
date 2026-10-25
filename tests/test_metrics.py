"""Unit tests for offline retrieval evaluation metrics."""

from ragdocs.eval.metrics import evidence_recall_at_k, hit_at_k, matches, mrr
from ragdocs.schemas import Chunk, Evidence, RetrievedChunk


def _make_chunk(chunk_id: str, doc_path: str, anchor: str) -> Chunk:
    """Helper to create dummy Chunk for metrics testing."""
    return Chunk(
        chunk_id=chunk_id,
        doc_path=doc_path,
        url=f"https://docs.langchain.com/{doc_path}#{anchor}",
        title="Test Title",
        heading_path=["Heading 1", "Heading 2"],
        anchor=anchor,
        text="Sample text content for chunk.",
        embed_text="Test Title > Heading 1 > Sample text",
        n_tokens=25,
        has_code=False,
        source_commit="testcommit",
    )


def _make_retrieved(
    chunk: Chunk, score: float, rank: int, retriever: str = "test"
) -> RetrievedChunk:
    """Helper to create RetrievedChunk."""
    return RetrievedChunk(chunk=chunk, score=score, rank=rank, retriever=retriever)


def test_matches_exact_and_mismatch() -> None:
    """Test matches function with identical and differing paths/anchors."""
    c1 = _make_chunk("c1", "guide/memory.mdx", "checkpointing")
    rc1 = _make_retrieved(c1, 0.9, 1)

    ev_match = Evidence(doc_path="guide/memory.mdx", anchor="checkpointing")
    ev_diff_path = Evidence(doc_path="guide/state.mdx", anchor="checkpointing")
    ev_diff_anchor = Evidence(doc_path="guide/memory.mdx", anchor="other")

    assert matches(c1, ev_match) is True
    assert matches(rc1, ev_match) is True
    assert matches(c1, ev_diff_path) is False
    assert matches(c1, ev_diff_anchor) is False


def test_hit_at_k_basic_and_cutoff() -> None:
    """Test hit_at_k at various k thresholds."""
    c1 = _make_chunk("c1", "doc1.mdx", "a1")
    c2 = _make_chunk("c2", "doc2.mdx", "a2")
    c3 = _make_chunk("c3", "doc3.mdx", "a3")

    retrieved = [
        _make_retrieved(c1, 0.9, 1),
        _make_retrieved(c2, 0.8, 2),
        _make_retrieved(c3, 0.7, 3),
    ]
    ev = [Evidence(doc_path="doc2.mdx", anchor="a2")]

    assert hit_at_k(retrieved, ev, k=1) == 0.0
    assert hit_at_k(retrieved, ev, k=2) == 1.0
    assert hit_at_k(retrieved, ev, k=5) == 1.0


def test_hit_at_k_edge_cases() -> None:
    """Test hit_at_k edge cases: empty lists, non-positive k, absent evidence."""
    c1 = _make_chunk("c1", "doc1.mdx", "a1")
    retrieved = [_make_retrieved(c1, 0.9, 1)]
    ev = [Evidence(doc_path="doc1.mdx", anchor="a1")]

    assert hit_at_k([], ev, k=5) == 0.0
    assert hit_at_k(retrieved, [], k=5) == 0.0
    assert hit_at_k(retrieved, ev, k=0) == 0.0
    assert hit_at_k(retrieved, ev, k=-1) == 0.0

    ev_absent = [Evidence(doc_path="missing.mdx", anchor="none")]
    assert hit_at_k(retrieved, ev_absent, k=5) == 0.0


def test_mrr_calculation_and_edge_cases() -> None:
    """Test MRR computation with single/multiple matches and absent cases."""
    c1 = _make_chunk("c1", "doc1.mdx", "a1")
    c2 = _make_chunk("c2", "doc2.mdx", "a2")
    c3 = _make_chunk("c3", "doc3.mdx", "a3")

    retrieved = [
        _make_retrieved(c1, 0.9, 1),
        _make_retrieved(c2, 0.8, 2),
        _make_retrieved(c3, 0.7, 3),
    ]

    # Rank 1 match
    assert mrr(retrieved, [Evidence(doc_path="doc1.mdx", anchor="a1")]) == 1.0
    # Rank 2 match
    assert mrr(retrieved, [Evidence(doc_path="doc2.mdx", anchor="a2")]) == 0.5
    # Rank 3 match
    assert mrr(retrieved, [Evidence(doc_path="doc3.mdx", anchor="a3")]) == 1.0 / 3.0

    # Multiple evidence matches: returns reciprocal of the first matching rank
    ev_multi = [
        Evidence(doc_path="doc3.mdx", anchor="a3"),
        Evidence(doc_path="doc2.mdx", anchor="a2"),
    ]
    assert mrr(retrieved, ev_multi) == 0.5

    # Absent evidence
    assert mrr(retrieved, [Evidence(doc_path="absent.mdx", anchor="none")]) == 0.0
    # Empty inputs
    assert mrr([], ev_multi) == 0.0
    assert mrr(retrieved, []) == 0.0


def test_evidence_recall_at_k_single_and_multi() -> None:
    """Test evidence_recall_at_k with single and multiple evidence items."""
    c1 = _make_chunk("c1", "doc1.mdx", "a1")
    c2 = _make_chunk("c2", "doc2.mdx", "a2")
    c3 = _make_chunk("c3", "doc3.mdx", "a3")

    retrieved = [
        _make_retrieved(c1, 0.9, 1),
        _make_retrieved(c2, 0.8, 2),
        _make_retrieved(c3, 0.7, 3),
    ]

    ev_single = [Evidence(doc_path="doc2.mdx", anchor="a2")]
    assert evidence_recall_at_k(retrieved, ev_single, k=1) == 0.0
    assert evidence_recall_at_k(retrieved, ev_single, k=2) == 1.0

    ev_multi = [
        Evidence(doc_path="doc1.mdx", anchor="a1"),
        Evidence(doc_path="doc3.mdx", anchor="a3"),
    ]
    # At k=1: only doc1 is retrieved (1/2 = 0.5)
    assert evidence_recall_at_k(retrieved, ev_multi, k=1) == 0.5
    # At k=2: still only doc1 is retrieved (1/2 = 0.5)
    assert evidence_recall_at_k(retrieved, ev_multi, k=2) == 0.5
    # At k=3: both doc1 and doc3 are retrieved (2/2 = 1.0)
    assert evidence_recall_at_k(retrieved, ev_multi, k=3) == 1.0

    # Edge cases
    assert evidence_recall_at_k([], ev_multi, k=5) == 0.0
    assert evidence_recall_at_k(retrieved, [], k=5) == 0.0
    assert evidence_recall_at_k(retrieved, ev_multi, k=0) == 0.0
