"""Unit tests for evaluation dataset validator."""

import json
from typing import Any

import pytest

from ragdocs.eval.absence import (
    build_term_regex,
    check_all_unanswerable_absence,
)
from ragdocs.eval.config import MIN_REAL_SOURCES
from ragdocs.eval.validate import (
    check_sources,
    find_4gram_overlaps,
    validate_eval_dataset,
)
from ragdocs.schemas import EvalItem, Evidence


@pytest.fixture
def tiny_chunks() -> list[dict[str, Any]]:
    """A small fixture corpus for testing."""
    return [
        {
            "chunk_id": "c001",
            "doc_path": "page1.mdx",
            "url": "https://docs.example.com/page1#section-a",
            "title": "Page One",
            "heading_path": ["Section A"],
            "anchor": "section-a",
            "text": "To configure the memory saver, pass SqliteSaver to compile method.",
            "embed_text": "To configure the memory saver, pass SqliteSaver to compile method.",
            "n_tokens": 15,
            "has_code": False,
            "source_commit": "abc1234",
        },
        {
            "chunk_id": "c002",
            "doc_path": "page2.mdx",
            "url": "https://docs.example.com/page2#section-b",
            "title": "Page Two",
            "heading_path": ["Section B"],
            "anchor": "section-b",
            "text": "StateGraph accepts state schema and returns compiled app with checkpointing.",
            "embed_text": "StateGraph accepts state schema and returns compiled app.",
            "n_tokens": 16,
            "has_code": False,
            "source_commit": "abc1234",
        },
        {
            "chunk_id": "c003",
            "doc_path": "page3.mdx",
            "url": "https://docs.example.com/page3#section-c",
            "title": "Page Three",
            "heading_path": ["Section C"],
            "anchor": "section-c",
            "text": "Use MemorySaver in memory instead of persistent storage for ephemeral runs.",
            "embed_text": "Use MemorySaver in memory instead of persistent storage.",
            "n_tokens": 14,
            "has_code": False,
            "source_commit": "abc1234",
        },
    ]


def make_valid_50_items() -> list[dict[str, Any]]:
    """Generate 50 valid eval item dicts across 16 pages."""
    items = []
    # 28 single
    for i in range(1, 29):
        page_idx = (i % 16) + 1
        items.append(
            {
                "id": f"q{i:03d}",
                "question": f"Developer inquiry unique phrasing {i} regarding state workflow?",
                "category": "single",
                "reference_answer": f"Use SqliteSaver to persist graph state in db run {i}.",
                "evidence": [{"doc_path": f"page{page_idx}.mdx", "anchor": "section-a"}],
                "must_mention": ["SqliteSaver"],
                "source": (
                    "https://github.com/langchain-ai/langgraph/issues/100"
                    if i <= MIN_REAL_SOURCES
                    else "docs"
                ),
                "notes": "",
                "verified": False,
            }
        )
    # 8 multi
    for i in range(29, 37):
        page_idx = (i % 16) + 1
        items.append(
            {
                "id": f"q{i:03d}",
                "question": f"How can multiple components connect together in step {i}?",
                "category": "multi",
                "reference_answer": f"Connect StateGraph components across checkpoints {i}.",
                "evidence": [
                    {"doc_path": f"page{page_idx}.mdx", "anchor": "section-a"},
                    {"doc_path": f"page{((page_idx + 1) % 16) + 1}.mdx", "anchor": "section-b"},
                ],
                "must_mention": ["StateGraph"],
                "source": "https://github.com/langchain-ai/langgraph/issues/200",
                "notes": "",
                "verified": False,
            }
        )
    # 6 version
    for i in range(37, 43):
        p = i - 36  # pages 1 to 6
        items.append(
            {
                "id": f"q{i:03d}",
                "question": f"What is the modern approach to initialize checkpoint store {i}?",
                "category": "version",
                "reference_answer": f"The modern way is MemorySaver instead of deprecated {i}.",
                "evidence": [{"doc_path": f"page{p}.mdx", "anchor": "section-c"}],
                "must_mention": ["MemorySaver"],
                "source": "docs",
                "notes": "Older versions used InMemorySaver.",
                "verified": False,
            }
        )
    # 8 unanswerable
    for i in range(43, 51):
        items.append(
            {
                "id": f"q{i:03d}",
                "question": f"Can I configure quantum entanglement clustering in step {i}?",
                "category": "unanswerable",
                "reference_answer": None,
                "evidence": [],
                "must_mention": [],
                "source": "docs",
                "notes": "Searches ran: quantum, entanglement, clustering",
                "verified": False,
            }
        )
    return items


def test_overlap_detection():
    """Verify 4-gram overlap detection catches identical 4-word runs."""
    evidence_text = "To configure the memory saver, pass SqliteSaver to compile method."
    # Overlapping 4-word run: "to configure the memory"
    question_with_overlap = "How to configure the memory saver in my application?"
    overlaps = find_4gram_overlaps(question_with_overlap, [evidence_text])
    assert "to configure the memory" in overlaps
    assert "configure the memory saver" in overlaps

    # No 4-word run overlap
    question_clean = "Where do I provide persistence when compiling my workflow?"
    clean_overlaps = find_4gram_overlaps(question_clean, [evidence_text])
    assert clean_overlaps == []


def test_unresolved_evidence_fails(tiny_chunks):
    """Verify that evidence with nonexistent doc_path or anchor fails validation."""
    items = make_valid_50_items()
    # Point first item to nonexistent doc_path and anchor
    items[0]["evidence"] = [{"doc_path": "nonexistent.mdx", "anchor": "fake-anchor"}]
    raw_lines = [json.dumps(it) for it in items]

    report = validate_eval_dataset(raw_lines, tiny_chunks, require_verified=False)
    assert not report.passed
    ev_check = next(c for c in report.checks if c.name == "Evidence resolution")
    assert not ev_check.passed
    assert "nonexistent.mdx#fake-anchor" in ev_check.details


def test_wrong_category_counts_fails(tiny_chunks):
    """Verify that dataset with incorrect category distribution fails validation."""
    items = make_valid_50_items()
    # Change one single item to multi (27 single, 9 multi)
    items[0]["category"] = "multi"
    items[0]["evidence"].append({"doc_path": "page2.mdx", "anchor": "section-b"})
    raw_lines = [json.dumps(it) for it in items]

    report = validate_eval_dataset(raw_lines, tiny_chunks, require_verified=False)
    assert not report.passed
    cat_check = next(c for c in report.checks if c.name == "Category composition")
    assert not cat_check.passed
    assert "single=27/28" in cat_check.details


def test_unanswerable_with_evidence_rejected():
    """Verify that an unanswerable item containing evidence fails validation."""
    with pytest.raises(ValueError, match="Unanswerable items must have empty evidence"):
        EvalItem(
            id="q043",
            question="Can LangGraph run on Ethereum?",
            category="unanswerable",
            reference_answer=None,
            evidence=[{"doc_path": "page1.mdx", "anchor": "sec"}],
            source="docs",
        )


def test_unanswerable_with_reference_answer_rejected():
    """Verify that an unanswerable item with reference_answer fails validation."""
    with pytest.raises(
        ValueError, match="Unanswerable items must have reference_answer set to None"
    ):
        EvalItem(
            id="q043",
            question="Can LangGraph run on Ethereum?",
            category="unanswerable",
            reference_answer="No it cannot.",
            evidence=[],
            source="docs",
        )


def test_require_verified_flag(tiny_chunks, tmp_path):
    """Verify that require_verified enforces verified=True across all items."""
    # Build 16 mock chunk pages to satisfy page spread and evidence resolution
    mock_chunks = []
    for p in range(1, 17):
        mock_chunks.extend(
            [
                {
                    "chunk_id": f"c_{p}_a",
                    "doc_path": f"page{p}.mdx",
                    "anchor": "section-a",
                    "text": "SqliteSaver persistence engine.",
                },
                {
                    "chunk_id": f"c_{p}_b",
                    "doc_path": f"page{p}.mdx",
                    "anchor": "section-b",
                    "text": "StateGraph graph builder.",
                },
            ]
        )
    for p in range(1, 7):
        mock_chunks.append(
            {
                "chunk_id": f"c_{p}_c",
                "doc_path": f"page{p}.mdx",
                "anchor": "section-c",
                "text": "MemorySaver in memory store.",
            }
        )

    items = make_valid_50_items()
    raw_lines = [json.dumps(it) for it in items]

    quotes_path = tmp_path / "source_quotes.json"
    snapshots_dir = tmp_path / "source_snapshots"
    snapshots_dir.mkdir()
    quotes_data = {}
    for it in items:
        if it["source"] != "docs":
            quotes_data[it["id"]] = {"url": it["source"]}
            (snapshots_dir / f"{it['id']}.txt").write_text("Title: Mock", encoding="utf-8")
    quotes_path.write_text(json.dumps(quotes_data), encoding="utf-8")

    # Without require_verified: passes
    report_unverified = validate_eval_dataset(
        raw_lines,
        mock_chunks,
        require_verified=False,
        quotes_path=quotes_path,
        snapshots_dir=snapshots_dir,
    )
    assert report_unverified.passed

    # With require_verified: fails because verified=False
    report_verified = validate_eval_dataset(
        raw_lines,
        mock_chunks,
        require_verified=True,
        quotes_path=quotes_path,
        snapshots_dir=snapshots_dir,
    )
    assert not report_verified.passed
    ver_check = next(c for c in report_verified.checks if c.name == "Verification status")
    assert not ver_check.passed
    assert "0/50" in ver_check.details


def test_check_sources_threshold():
    """Verify check_sources enforces MIN_REAL_SOURCES."""
    # When real sources == MIN_REAL_SOURCES: passes
    items_pass = [
        EvalItem(
            id=f"q{i:03d}",
            question=f"Question {i}?",
            category="single",
            reference_answer="Answer.",
            evidence=[Evidence(doc_path="page1.mdx", anchor="sec1")],
            must_mention=["ident"],
            source="https://forum.example.com/t/123" if i <= MIN_REAL_SOURCES else "docs",
            verified=False,
        )
        for i in range(1, 43)
    ]
    ok_pass, details_pass = check_sources(items_pass)
    assert ok_pass
    assert f"{MIN_REAL_SOURCES}/42 answerable items adapted from real user sources" in details_pass

    # When real sources == MIN_REAL_SOURCES - 1: fails
    items_fail = [
        EvalItem(
            id=f"q{i:03d}",
            question=f"Question {i}?",
            category="single",
            reference_answer="Answer.",
            evidence=[Evidence(doc_path="page1.mdx", anchor="sec1")],
            must_mention=["ident"],
            source="https://forum.example.com/t/123" if i < MIN_REAL_SOURCES else "docs",
            verified=False,
        )
        for i in range(1, 43)
    ]
    ok_fail, details_fail = check_sources(items_fail)
    assert not ok_fail
    assert f"Only {MIN_REAL_SOURCES - 1}/42" in details_fail
    assert f"minimum {MIN_REAL_SOURCES} required" in details_fail


def test_absence_word_boundary_matching():
    """Verify regex respects word boundaries ('pod' vs 'podcast', 'tripod')."""
    pattern = build_term_regex("pod")
    assert pattern.search("Deploying inside a pod container.") is not None
    assert pattern.search("This is a pod.") is not None
    assert pattern.search("Running (pod) test.") is not None
    assert pattern.search("Listen to our podcast episode.") is None
    assert pattern.search("Mounted on a tripod.") is None
    assert pattern.search("Variable pod_count set.") is None


def test_absence_case_insensitivity():
    """Verify term matching is case-insensitive."""
    pattern = build_term_regex("cuda")
    assert pattern.search("Enable CUDA acceleration.") is not None
    assert pattern.search("Cuda device mapping.") is not None
    assert pattern.search("cuda support.") is not None


def test_absence_multi_word_terms():
    """Verify multi-word and hyphenated term matching."""
    ws_pattern = build_term_regex("web socket")
    assert ws_pattern.search("Use a web socket connection.") is not None
    assert ws_pattern.search("Use a web    socket connection.") is not None
    assert ws_pattern.search("Use a websocket connection.") is None

    hs_pattern = build_term_regex("hot-swap")
    assert hs_pattern.search("Perform a hot-swap operation.") is not None
    assert hs_pattern.search("A hot-swappable module.") is None


def test_absence_uncleared_hit_fails():
    """Verify an unadjudicated term hit causes failure."""
    chunk = {
        "chunk_id": "c_gpu_01",
        "doc_path": "gpu.mdx",
        "anchor": "setup",
        "url": "https://docs.example.com/gpu#setup",
        "text": "Requires CUDA drivers installed on the host.",
    }
    items = [
        EvalItem(
            id="q043",
            question="How to configure CUDA device pinning?",
            category="unanswerable",
            reference_answer=None,
            evidence=[],
            source="docs",
        )
    ]
    terms_map = {"q043": ["cuda"]}
    adjudications_map = {}

    result = check_all_unanswerable_absence(items, [chunk], terms_map, adjudications_map)
    assert not result.passed
    assert len(result.errors) == 1
    assert "c_gpu_01" in result.errors[0]


def test_absence_adjudicated_hit_passes():
    """Verify an adjudicated irrelevant hit passes absence verification."""
    chunk = {
        "chunk_id": "c_gpu_01",
        "doc_path": "gpu.mdx",
        "anchor": "setup",
        "url": "https://docs.example.com/gpu#setup",
        "text": "Requires CUDA drivers installed on the host.",
    }
    items = [
        EvalItem(
            id="q043",
            question="How to configure CUDA device pinning?",
            category="unanswerable",
            reference_answer=None,
            evidence=[],
            source="docs",
        )
    ]
    terms_map = {"q043": ["cuda"]}
    adjudications_map = {
        "q043": [
            {
                "term": "cuda",
                "chunk_id": "c_gpu_01",
                "verdict": "irrelevant",
                "reason": "Reference is to host driver prerequisites not node configuration.",
            }
        ]
    }

    result = check_all_unanswerable_absence(items, [chunk], terms_map, adjudications_map)
    assert result.passed
    hits = result.item_hits["q043"]["cuda"]
    assert len(hits) == 1
    assert hits[0].cleared is True


def test_absence_missing_terms_entry_fails():
    """Verify missing absence_terms entry causes failure."""
    items = [
        EvalItem(
            id="q043",
            question="How to configure CUDA device pinning?",
            category="unanswerable",
            reference_answer=None,
            evidence=[],
            source="docs",
        )
    ]
    result = check_all_unanswerable_absence(items, [], {}, {})
    assert not result.passed
    assert any("Missing absence terms" in err for err in result.errors)


def test_must_mention_evidence_only(tiny_chunks):
    """Verify must_mention must appear in evidence chunks, not merely anywhere in the corpus."""
    # tiny_chunks[0] has 'SqliteSaver', tiny_chunks[1] has 'StateGraph'
    items = make_valid_50_items()
    # Change q001 evidence to page1 (which has SqliteSaver), but set must_mention to 'StateGraph'
    # 'StateGraph' exists in the corpus (page2), but NOT in q001's evidence (page1).
    items[0]["must_mention"] = ["StateGraph"]
    raw_lines = [json.dumps(it) for it in items]

    report = validate_eval_dataset(raw_lines, tiny_chunks, require_verified=False)
    assert not report.passed
    mm_check = next(c for c in report.checks if c.name == "Must-mention identifiers")
    assert not mm_check.passed
    assert "q001: 'StateGraph' not found in evidence chunks" in mm_check.details


def test_4gram_overlap_case_insensitive():
    """Verify 4-gram overlap catches mixed-case matches that match only after lowercasing."""
    evidence_text = "To configure the memory saver, pass SqliteSaver to compile method."
    # Mixed-case overlap with evidence: "TO CONFIGURE THE MEMORY" vs "To configure the memory"
    question_mixed = "HOW TO CONFIGURE THE MEMORY SAVER IN PRODUCTION?"
    overlaps = find_4gram_overlaps(question_mixed, [evidence_text])
    assert "to configure the memory" in overlaps
