"""Unit tests for answer generation, validation, and baseline pipeline execution."""

from typing import Any

import pytest

from ragdocs.generation.answer import (
    AnswerDraft,
    StructuredLLM,
    format_context,
    generate_answer,
    validate_answer,
)
from ragdocs.generation.prompts import ABSTAIN_TEXT
from ragdocs.pipelines.base import run
from ragdocs.pipelines.baseline import BaselinePipeline
from ragdocs.pipelines.registry import clear_pipeline_cache, get_pipeline, list_pipelines
from ragdocs.providers.llm import CallCounter
from ragdocs.schemas import Chunk, PipelineResult, RetrievedChunk, TraceEvent


def _make_dummy_chunk(chunk_id: str, title: str, path: str = "doc.mdx") -> Chunk:
    """Helper to construct dummy Chunk objects."""
    return Chunk(
        chunk_id=chunk_id,
        doc_path=path,
        url=f"https://docs.langchain.com/{path}",
        title=title,
        heading_path=["Section", "Subsection"],
        anchor="sec",
        text=f"Text content for chunk {chunk_id}.",
        embed_text=f"{title}: Text content for chunk {chunk_id}.",
        n_tokens=10,
        has_code=False,
        source_commit="commit-1",
    )


def _make_dummy_retrieved_chunk(
    chunk_id: str,
    title: str,
    rank: int = 1,
    score: float = 0.95,
) -> RetrievedChunk:
    """Helper to construct dummy RetrievedChunk objects."""
    return RetrievedChunk(
        chunk=_make_dummy_chunk(chunk_id, title),
        score=score,
        rank=rank,
        retriever="hybrid",
    )


class StubStructuredLLM:
    """Stub StructuredLLM returning predetermined AnswerDraft without network."""

    def __init__(self, draft: AnswerDraft) -> None:
        self.draft = draft
        self.invoked_with: Any = None

    def invoke(self, messages: Any, **kwargs: Any) -> AnswerDraft:
        self.invoked_with = messages
        return self.draft


class StubRetriever:
    """Stub retriever returning fixed chunks."""

    def __init__(self, chunks: list[RetrievedChunk], mode: str = "hybrid") -> None:
        self.chunks = chunks
        self.mode = mode

    def retrieve(self, query: str, mode: str | None = None) -> list[RetrievedChunk]:
        return self.chunks


class ErrorRetriever:
    """Retriever stub that raises an exception during retrieval."""

    def retrieve(self, query: str, mode: str | None = None) -> list[RetrievedChunk]:
        raise RuntimeError("Simulated database failure with secret_api_key_12345")


def test_format_context_numbering_and_structure() -> None:
    """Context format matches '[n] {title} > {heading path joined by ' > '} ({url})'."""
    chunks = [
        _make_dummy_retrieved_chunk("chk-01", "Overview", rank=1),
        _make_dummy_retrieved_chunk("chk-02", "Advanced", rank=2),
    ]
    formatted = format_context(chunks)
    assert "[1] Overview > Section > Subsection (https://docs.langchain.com/doc.mdx)" in formatted
    assert "[2] Advanced > Section > Subsection (https://docs.langchain.com/doc.mdx)" in formatted
    assert "Text content for chunk chk-01." in formatted
    assert "\n\n[2]" in formatted


def test_valid_citations_mapped_to_chunk_ids() -> None:
    """Valid citations map 1-based indices to matching Chunk chunk_id and url."""
    chunks = [
        _make_dummy_retrieved_chunk("chk-01", "Chunk 1"),
        _make_dummy_retrieved_chunk("chk-02", "Chunk 2"),
    ]
    draft = AnswerDraft(
        answer="Fact one [1]. Fact two [2].",
        cited=[1, 2],
        abstain=False,
    )
    answer, diag = validate_answer(draft, chunks)

    assert not answer.abstained
    assert len(answer.citations) == 2
    assert answer.citations[0].chunk_id == "chk-01"
    assert answer.citations[0].url == "https://docs.langchain.com/doc.mdx"
    assert answer.citations[1].chunk_id == "chk-02"
    assert diag["dropped_citations"] == 0
    assert not diag["uncited"]


def test_out_of_range_citation_dropped_and_marker_removed() -> None:
    """Out-of-range citations are dropped from cited list and markers removed from text."""
    chunks = [
        _make_dummy_retrieved_chunk("chk-01", "Chunk 1"),
    ]
    draft = AnswerDraft(
        answer="Valid statement [1], but invalid fact [99] and zero [0].",
        cited=[1, 99, 0],
        abstain=False,
    )
    answer, diag = validate_answer(draft, chunks)

    assert len(answer.citations) == 1
    assert answer.citations[0].chunk_id == "chk-01"
    assert diag["dropped_citations"] == 2
    assert "[99]" not in answer.text
    assert "[0]" not in answer.text
    assert "[1]" in answer.text
    assert "Valid statement [1], but invalid fact and zero." in answer.text


def test_duplicate_citations_deduplicated_preserving_order() -> None:
    """Duplicate citation indices are collapsed preserving first occurrence."""
    chunks = [
        _make_dummy_retrieved_chunk("chk-01", "Chunk 1"),
        _make_dummy_retrieved_chunk("chk-02", "Chunk 2"),
    ]
    draft = AnswerDraft(
        answer="Duplicate reference [2] and again [2] and [1].",
        cited=[2, 2, 1, 2],
        abstain=False,
    )
    answer, diag = validate_answer(draft, chunks)

    assert len(answer.citations) == 2
    assert answer.citations[0].chunk_id == "chk-02"
    assert answer.citations[1].chunk_id == "chk-01"
    assert diag["dropped_citations"] == 0


def test_abstain_forces_abstain_text_and_empty_citations() -> None:
    """When abstain is True, text is set to ABSTAIN_TEXT and citations are emptied."""
    chunks = [
        _make_dummy_retrieved_chunk("chk-01", "Chunk 1"),
    ]
    draft = AnswerDraft(
        answer="Something else was generated [1].",
        cited=[1],
        abstain=True,
    )
    answer, diag = validate_answer(draft, chunks)

    assert answer.abstained
    assert answer.text == ABSTAIN_TEXT
    assert answer.citations == []
    assert not diag["uncited"]


def test_uncited_flag_when_not_abstaining() -> None:
    """uncited diagnostic is True when not abstaining and no valid citations remain."""
    chunks = [
        _make_dummy_retrieved_chunk("chk-01", "Chunk 1"),
    ]
    # No citations in draft
    draft_no_cite = AnswerDraft(
        answer="A fact with no citation.",
        cited=[],
        abstain=False,
    )
    _, diag1 = validate_answer(draft_no_cite, chunks)
    assert diag1["uncited"] is True

    # Only invalid citation
    draft_invalid = AnswerDraft(
        answer="A fact with bad citation [42].",
        cited=[42],
        abstain=False,
    )
    _, diag2 = validate_answer(draft_invalid, chunks)
    assert diag2["uncited"] is True
    assert diag2["dropped_citations"] == 1


def test_baseline_stream_event_order_and_final_answer_result() -> None:
    """Stream yields events in exact expected order and final event parses as PipelineResult."""
    chunks = [
        _make_dummy_retrieved_chunk("chk-01", "Chunk 1", rank=1),
    ]
    draft = AnswerDraft(
        answer="LangGraph state is manageable [1].",
        cited=[1],
        abstain=False,
    )
    pipeline = BaselinePipeline(
        retriever=StubRetriever(chunks),
        structured_llm=StubStructuredLLM(draft),
    )

    events: list[TraceEvent] = list(pipeline.stream("How to manage state?"))

    assert len(events) == 5
    assert events[0].type == "node_start" and events[0].node == "retrieve"
    assert events[1].type == "retrieval" and events[1].node == "retrieve"
    assert events[1].data["mode"] == "hybrid"
    assert len(events[1].data["chunks"]) == 1
    assert events[1].data["chunks"][0]["title"] == "Chunk 1"
    assert events[2].type == "node_start" and events[2].node == "generate"
    assert events[3].type == "node_end" and events[3].node == "generate"
    assert "dropped_citations" in events[3].data
    assert events[4].type == "answer" and events[4].node == "answer"

    # Verify all events carry monotonic non-negative t_ms
    for ev in events:
        assert ev.t_ms >= 0

    # Parse final PipelineResult
    result = PipelineResult.model_validate(events[4].data)
    assert result.question == "How to manage state?"
    assert result.pipeline == "baseline"
    assert result.answer.text == "LangGraph state is manageable [1]."
    assert len(result.answer.citations) == 1
    assert result.answer.citations[0].chunk_id == "chk-01"


def test_run_helper_consumes_stream_and_returns_result() -> None:
    """run() consumes stream and returns parsed PipelineResult."""
    chunks = [_make_dummy_retrieved_chunk("chk-01", "Chunk 1")]
    draft = AnswerDraft(answer="Result [1].", cited=[1], abstain=False)
    pipeline = BaselinePipeline(
        retriever=StubRetriever(chunks),
        structured_llm=StubStructuredLLM(draft),
    )
    res = run(pipeline, "Test query?")
    assert isinstance(res, PipelineResult)
    assert res.answer.text == "Result [1]."


def test_stream_error_path_yields_one_error_event_no_exception_escaping() -> None:
    """On exception during execution, stream yields one error event without escaping exception."""
    pipeline = BaselinePipeline(
        retriever=ErrorRetriever(),
        structured_llm=StubStructuredLLM(AnswerDraft(answer="a", cited=[], abstain=False)),
    )

    # Must not raise an unhandled exception
    events = list(pipeline.stream("Failing query"))
    assert len(events) == 2
    assert events[0].type == "node_start"
    assert events[1].type == "error"
    assert "Simulated database failure" in events[1].message
    # Verify no stack trace or secrets leaked
    assert "Traceback" not in events[1].message
    assert "\n" not in events[1].message


def test_run_helper_raises_on_error_event() -> None:
    """run() raises RuntimeError when stream produces an error event."""
    pipeline = BaselinePipeline(
        retriever=ErrorRetriever(),
        structured_llm=StubStructuredLLM(AnswerDraft(answer="a", cited=[], abstain=False)),
    )
    with pytest.raises(RuntimeError) as exc_info:
        run(pipeline, "Failing query")
    assert "Simulated database failure" in str(exc_info.value)


def test_registry_list_and_unknown_pipeline_error_message() -> None:
    """Registry lists available pipelines and raises clear error for unknown names."""
    clear_pipeline_cache()
    available = list_pipelines()
    assert "baseline" in available

    with pytest.raises(ValueError) as exc_info:
        get_pipeline("non_existent_pipeline")

    err = str(exc_info.value)
    assert "Unknown pipeline 'non_existent_pipeline'" in err
    assert "baseline" in err


def test_call_counter_deduplication() -> None:
    """CallCounter correctly tracks LLM and chat model calls without double-counting."""
    from uuid import uuid4

    counter = CallCounter()
    run_id = uuid4()

    counter.on_chat_model_start({}, [[]], run_id=run_id)
    counter.on_llm_start({}, [], run_id=run_id)  # same run_id must not double count
    assert counter.llm_calls == 1

    run_id_2 = uuid4()
    counter.on_chat_model_start({}, [[]], run_id=run_id_2)
    assert counter.llm_calls == 2


def test_generate_answer_invokes_structured_llm_and_validates() -> None:
    """generate_answer builds prompt messages, invokes StructuredLLM, and returns Answer."""
    chunks = [_make_dummy_retrieved_chunk("chk-01", "Chunk 1")]
    draft = AnswerDraft(answer="Direct answer [1].", cited=[1], abstain=False)
    stub_llm: StructuredLLM = StubStructuredLLM(draft)

    answer, diag = generate_answer("What is this?", chunks, stub_llm)
    assert answer.text == "Direct answer [1]."
    assert len(answer.citations) == 1
    assert answer.citations[0].chunk_id == "chk-01"
    assert not diag["uncited"]
