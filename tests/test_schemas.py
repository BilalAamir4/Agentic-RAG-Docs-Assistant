"""Tests for pydantic schema validation."""

import pytest
from pydantic import ValidationError

from ragdocs.schemas import Chunk, EvalItem, Evidence


def test_chunk_doc_path_normalization() -> None:
    """Chunk doc_path should normalize backslashes to forward slashes."""
    chunk = Chunk(
        chunk_id="c001",
        doc_path=r"concepts\graphs\state.md",
        url="https://langchain-ai.github.io/langgraph/concepts/graphs/#state",
        title="State Graph",
        heading_path=["Graphs", "State"],
        anchor="#state",
        text="State represents the graph memory.",
        embed_text="State Graph: State represents the graph memory.",
        n_tokens=10,
        has_code=False,
        source_commit="abcdef0",
    )
    assert chunk.doc_path == "concepts/graphs/state.md"


def test_eval_item_valid_answerable() -> None:
    """EvalItem validator accepts valid answerable items."""
    item = EvalItem(
        id="q001",
        question="How does state management work in LangGraph?",
        category="single",
        reference_answer="State is managed via state schemas.",
        evidence=[Evidence(doc_path="concepts/state.md", anchor="#schemas")],
        must_mention=["state schema"],
        source="docs",
        verified=True,
    )
    assert item.id == "q001"
    assert item.reference_answer is not None
    assert len(item.evidence) == 1


def test_eval_item_valid_unanswerable() -> None:
    """EvalItem validator accepts valid unanswerable items."""
    item = EvalItem(
        id="q002",
        question="How do I configure quantum computing nodes?",
        category="unanswerable",
        reference_answer=None,
        evidence=[],
        source="out-of-scope",
    )
    assert item.id == "q002"
    assert item.reference_answer is None
    assert len(item.evidence) == 0


def test_eval_item_rejects_unanswerable_with_evidence() -> None:
    """EvalItem validator rejects unanswerable items containing evidence."""
    with pytest.raises(ValidationError) as exc_info:
        EvalItem(
            id="q003",
            question="What is the quantum state?",
            category="unanswerable",
            reference_answer=None,
            evidence=[Evidence(doc_path="concepts/state.md", anchor="#state")],
            source="test",
        )
    assert "Unanswerable items must have empty evidence" in str(exc_info.value)


def test_eval_item_rejects_unanswerable_with_reference_answer() -> None:
    """EvalItem validator rejects unanswerable items containing a reference answer."""
    with pytest.raises(ValidationError) as exc_info:
        EvalItem(
            id="q004",
            question="What is the quantum state?",
            category="unanswerable",
            reference_answer="It does not exist.",
            evidence=[],
            source="test",
        )
    assert "Unanswerable items must have reference_answer set to None" in str(exc_info.value)


def test_eval_item_rejects_answerable_without_evidence() -> None:
    """EvalItem validator rejects answerable items with empty evidence."""
    with pytest.raises(ValidationError) as exc_info:
        EvalItem(
            id="q005",
            question="How do I define a node?",
            category="single",
            reference_answer="Define nodes as functions.",
            evidence=[],
            source="test",
        )
    assert "must have at least one evidence entry" in str(exc_info.value)


def test_eval_item_rejects_answerable_without_reference_answer() -> None:
    """EvalItem validator rejects answerable items with missing or empty reference answer."""
    with pytest.raises(ValidationError) as exc_info:
        EvalItem(
            id="q006",
            question="How do I define a node?",
            category="multi",
            reference_answer=None,
            evidence=[Evidence(doc_path="concepts/nodes.md", anchor="#def")],
            source="test",
        )
    assert "must have a non-empty reference_answer" in str(exc_info.value)


def test_eval_item_rejects_invalid_id_pattern() -> None:
    """EvalItem validator rejects identifiers not matching ^q\\d{3}$."""
    with pytest.raises(ValidationError):
        EvalItem(
            id="question_1",
            question="Valid question text?",
            category="single",
            reference_answer="Valid reference answer.",
            evidence=[Evidence(doc_path="doc.md", anchor="#a")],
            source="test",
        )
