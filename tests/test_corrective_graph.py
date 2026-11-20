"""Corrective graph paths, LLM call bounds and decision events (M10 S2). Fakes only."""

from agentic_fakes import (
    QUESTION,
    FakeRetriever,
    Harness,
    answer,
    chunks,
    decisions,
    grades,
    node_path,
    rewrite,
)
from langchain_core.messages import HumanMessage

from ragdocs.generation.answer import format_context
from ragdocs.generation.prompts import ABSTAIN_TEXT, ANSWER_USER_TEMPLATE
from ragdocs.pipelines.agentic.state import OUTCOMES

NONE_RELEVANT = grades(False, False, False, False, False)


def _worst_case() -> Harness:
    return Harness(
        FakeRetriever(chunks(1, 2, 3, 4, 5), chunks(6, 7, 8, 9, 10)),
        grader=[NONE_RELEVANT, NONE_RELEVANT],
        rewriter=[rewrite("StateGraph compile checkpointer InMemorySaver")],
        generator=[answer([1])],
    )


def _assert_generator_saw_contexts(h: Harness, result) -> None:
    """The generator's user message was built from exactly result.contexts."""
    assert len(h.generator.received) == 1
    human = [m for m in h.generator.received[0] if isinstance(m, HumanMessage)][0]
    expected = ANSWER_USER_TEMPLATE.format(
        question=QUESTION, context=format_context(result.contexts)
    )
    assert human.content == expected


def test_all_relevant_goes_straight_to_generate_with_two_calls() -> None:
    h = Harness(
        FakeRetriever(chunks(1, 2, 3, 4, 5)),
        grader=[grades(True, True, True, True, True)],
        generator=[answer([1, 2])],
    )
    events, result = h.run()
    assert node_path(events) == ["retrieve", "grade_documents", "generate"]
    assert result.llm_calls == 2
    assert result.pipeline == "corrective"
    assert not result.used_web
    assert [c.chunk.chunk_id for c in result.contexts] == ["c1", "c2", "c3", "c4", "c5"]
    _assert_generator_saw_contexts(h, result)
    d = decisions(events)
    assert d[0].message == "5 of 5 chunks relevant" and d[0].data["outcome"] == "ok"
    assert d[1].data == {"branch": "generate", "outcome": "ok"}
    assert d[2].node == "generate" and d[2].data["outcome"] == "info"


def test_relevant_after_one_rewrite_uses_four_calls() -> None:
    h = Harness(
        FakeRetriever(chunks(1, 2, 3, 4, 5), chunks(6, 7, 8, 9, 10)),
        grader=[NONE_RELEVANT, grades(False, True, False, True, False)],
        rewriter=[rewrite("checkpointer compile")],
        generator=[answer([1])],
    )
    events, result = h.run()
    assert node_path(events) == [
        "retrieve", "grade_documents", "rewrite_query", "retrieve", "grade_documents", "generate",
    ]  # fmt: skip
    assert result.llm_calls == 4
    assert h.retriever.queries == [QUESTION, "checkpointer compile"]
    assert [c.chunk.chunk_id for c in result.contexts] == ["c7", "c9"]
    assert not result.used_web
    _assert_generator_saw_contexts(h, result)


def test_zero_relevant_twice_falls_back_to_web_then_generates() -> None:
    h = _worst_case()
    events, result = h.run()
    assert node_path(events) == [
        "retrieve", "grade_documents", "rewrite_query", "retrieve", "grade_documents",
        "web_search", "generate",
    ]  # fmt: skip
    assert result.used_web
    assert h.web.queries == [QUESTION]  # the original question, not the rewritten query
    assert [c.retriever for c in result.contexts] == ["web", "web"]
    _assert_generator_saw_contexts(h, result)


def test_worst_case_is_exactly_four_llm_calls() -> None:
    h = _worst_case()
    _, result = h.run()
    assert result.llm_calls == 4
    calls = [len(m.received) for m in (h.grader, h.rewriter, h.generator)]
    assert calls == [2, 1, 1]


def test_empty_web_results_abstain_without_generation() -> None:
    h = Harness(
        FakeRetriever(chunks(1, 2, 3, 4, 5)),
        grader=[NONE_RELEVANT, NONE_RELEVANT],
        rewriter=[rewrite("other query")],
        web=[],
    )
    events, result = h.run()
    assert result.answer.abstained
    assert result.answer.text == ABSTAIN_TEXT
    assert result.answer.citations == []
    assert result.contexts == []
    assert h.generator.received == []
    assert result.llm_calls == 3
    d = decisions(events)
    web = [e for e in d if e.node == "web_search"][0]
    assert web.message == "fell back to web search" and web.data["outcome"] == "stop"
    assert d[-1].node == "generate" and d[-1].data["outcome"] == "stop"


def test_relevant_chunks_deduplicated_across_retries_in_order() -> None:
    h = Harness(
        FakeRetriever(chunks(1, 2, 3, 4, 5), chunks(6, 1, 7, 8, 9)),
        grader=[grades(True, False, False, False, False), grades(True, True, True, False, False)],
        rewriter=[rewrite("second query")],
        generator=[answer([1])],
        min_relevant_chunks=3,
    )
    _, result = h.run()
    assert [c.chunk.chunk_id for c in result.contexts] == ["c1", "c6", "c7"]


def test_grading_always_uses_the_original_question() -> None:
    h = _worst_case()
    h.run()
    assert len(h.grader.received) == 2
    for messages in h.grader.received:
        human = [m for m in messages if isinstance(m, HumanMessage)][0]
        assert human.content.startswith(f"Question: {QUESTION}\n\nExcerpts:\n[1] ")
        assert "InMemorySaver" not in human.content


def test_decision_events_cover_every_route_with_valid_outcomes() -> None:
    events, _ = _worst_case().run()
    d = decisions(events)
    assert all(e.data["outcome"] in OUTCOMES for e in d)
    routes = [e for e in d if "branch" in e.data]
    n_grading = sum(1 for e in events if e.type == "node_start" and e.node == "grade_documents")
    assert len(routes) == n_grading == 2
    by_message = [(e.node, e.message, e.data["outcome"]) for e in d]
    assert by_message[0] == ("grade_documents", "0 of 5 chunks relevant", "retry")
    assert routes[0].data == {"branch": "rewrite_query", "outcome": "retry"}
    assert ("rewrite_query", "query rewritten", "retry") in by_message
    assert routes[1].data == {"branch": "web_search", "outcome": "retry"}
    assert ("web_search", "fell back to web search", "retry") in by_message
    assert by_message[-1][0] == "generate" and by_message[-1][2] == "info"


def test_every_node_emits_start_and_end() -> None:
    events, _ = _worst_case().run()
    starts = [e.node for e in events if e.type == "node_start"]
    ends = [e.node for e in events if e.type == "node_end"]
    assert starts == ends


def test_retrieval_event_carries_chunk_id_url_rank_score() -> None:
    events, _ = _worst_case().run()
    retrievals = [e for e in events if e.type == "retrieval"]
    assert len(retrievals) == 2
    first = retrievals[0].data["chunks"]
    assert [c["chunk_id"] for c in first] == ["c1", "c2", "c3", "c4", "c5"]
    for c in first + retrievals[1].data["chunks"]:
        assert {"chunk_id", "url", "rank", "score", "title", "heading_path"} <= set(c)
        assert c["url"] and c["chunk_id"]
    assert [c["rank"] for c in first] == [1, 2, 3, 4, 5]
