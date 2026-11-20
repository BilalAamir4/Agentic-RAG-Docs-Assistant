"""Corrective node functions called directly: grading edge cases, rewrite, web chunks (M10 S2)."""

import hashlib
import json
import re
from typing import Any

import pytest
from agentic_fakes import (
    QUESTION,
    WEB_RESULTS,
    FakeRetriever,
    FakeWebSearch,
    Harness,
    chunks,
    grades,
    rewrite,
)

from ragdocs.pipelines.agentic import nodes
from ragdocs.pipelines.agentic.state import AgentState, initial_state
from ragdocs.schemas import Evidence


def _state(**update: Any) -> AgentState:
    state = initial_state(QUESTION)
    state.update(update)  # type: ignore[typeddict-item]
    return state


def _harness(grader: list[str], rewriter: list[str] | None = None, **kw: Any) -> Harness:
    return Harness(FakeRetriever(chunks(1)), grader=grader, rewriter=rewriter, **kw)


def test_missing_out_of_range_and_duplicate_grades_are_not_relevant() -> None:
    raw = json.dumps({"grades": [
        {"index": 1, "relevant": True, "reason": "first wins"},
        {"index": 1, "relevant": False, "reason": "duplicate"},
        {"index": 9, "relevant": True, "reason": "out of range"},
        {"index": 0, "relevant": True, "reason": "out of range"},
        {"index": 3, "relevant": False, "reason": "no"},
    ]})  # fmt: skip
    h = _harness([raw])
    out = nodes.grade_documents(_state(documents=chunks(1, 2, 3, 4)), h.deps)
    assert [c.chunk.chunk_id for c in out["relevant"]] == ["c1"]
    assert out["diagnostics"]["missing_grades"] == 2  # excerpts 2 and 4
    assert out["diagnostics"]["invalid_grades"] == 3
    rows = out["events"][1].data["grades"]
    assert [r["relevant"] for r in rows] == [True, False, False, False]
    assert rows[0]["reason"] == "first wins"
    assert out["events"][1].message == "1 of 4 chunks relevant"


def test_grading_parse_error_marks_all_not_relevant_and_is_counted() -> None:
    h = _harness(["not json at all"])
    state = _state(documents=chunks(1, 2, 3), diagnostics={"grading_failures": 1})
    out = nodes.grade_documents(state, h.deps)
    assert out["relevant"] == []
    assert out["diagnostics"]["grading_failures"] == 2
    event = out["events"][1]
    assert event.message.startswith("0 of 3 chunks relevant (grading failed: OutputParserException")
    assert event.data["outcome"] == "retry" and event.data["grading_failed"] is True
    assert out["next_step"] == "rewrite_query"


def test_non_parse_errors_propagate() -> None:
    class Boom:
        def invoke(self, *_: Any, **__: Any) -> Any:
            raise ConnectionError("network")

    h = _harness([])
    h.deps.grader_llm = Boom()
    with pytest.raises(ConnectionError):
        nodes.grade_documents(_state(documents=chunks(1)), h.deps)


def test_grading_appends_deduplicated_in_order() -> None:
    h = _harness([grades(True, True, True)])
    state = _state(documents=chunks(3, 1, 4), relevant=chunks(1, 2))
    out = nodes.grade_documents(state, h.deps)
    assert [c.chunk.chunk_id for c in out["relevant"]] == ["c1", "c2", "c3", "c4"]


@pytest.mark.parametrize(
    ("n_relevant", "rewrites", "branch"),
    [(1, 0, "generate"), (0, 0, "rewrite_query"), (0, 1, "web_search")],
)
def test_route_decision(n_relevant: int, rewrites: int, branch: str) -> None:
    h = _harness([])
    assert nodes.route_decision(n_relevant, rewrites, h.settings)[0] == branch


def test_rewrite_uses_headings_and_counts() -> None:
    h = _harness([], rewriter=[rewrite("  StateGraph checkpointer  ")])
    docs = chunks(1, 2)
    out = nodes.rewrite_query(_state(documents=docs), h.deps)
    assert out["query"] == "StateGraph checkpointer"
    assert out["rewrites"] == 1
    human = h.rewriter.received[0][1].content
    assert human.endswith("all judged not relevant:\n1. Title 1 > H1\n2. Title 2 > H2")
    assert f"Question: {QUESTION}\nPrevious query: {QUESTION}\n" in human
    d = out["events"][1]
    assert d.message == "query rewritten"
    assert d.data == {
        "old_query": QUESTION, "new_query": "StateGraph checkpointer",
        "unchanged": False, "outcome": "retry",
    }  # fmt: skip


@pytest.mark.parametrize("new", ["", "   ", QUESTION.upper()])
def test_rewrite_unchanged_keeps_old_query(new: str) -> None:
    h = _harness([], rewriter=[rewrite(new)])
    out = nodes.rewrite_query(_state(documents=chunks(1)), h.deps)
    assert out["query"] == QUESTION
    assert out["diagnostics"]["rewrite_unchanged"] is True
    assert out["rewrites"] == 1


def test_web_chunk_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_ref(url: str) -> Evidence | None:
        seen.append(url)
        return Evidence(doc_path="persistence.mdx", anchor="") if "langgraph" in url else None

    monkeypatch.setattr(nodes, "url_to_doc_ref", fake_ref)
    h = _harness([])
    out = nodes.web_search(_state(), h.deps)
    assert seen == [r["url"] for r in WEB_RESULTS]
    first, second = out["web_docs"]
    for i, rc in enumerate(out["web_docs"]):
        url = WEB_RESULTS[i]["url"]
        assert re.fullmatch(r"web-[0-9a-f]{12}", rc.chunk.chunk_id)
        assert rc.chunk.chunk_id == "web-" + hashlib.sha1(url.encode()).hexdigest()[:12]
        assert rc.rank == i + 1 and rc.retriever == "web" and rc.score == 0.0
        assert rc.chunk.source_commit == "web" and rc.chunk.heading_path == []
        assert rc.chunk.embed_text == rc.chunk.text
    assert (first.chunk.doc_path, first.chunk.anchor) == ("persistence.mdx", "")
    assert second.chunk.doc_path == "web:/oss/python/langchain/human-in-the-loop"
    assert second.chunk.anchor == ""
    assert len(second.chunk.text) == 1800
    assert second.chunk.n_tokens == 450
    assert out["used_web"] is True


def test_web_chunk_score_code_and_token_estimate() -> None:
    rc = nodes.web_result_to_chunk(
        {"url": "https://example.com/a", "title": "t", "content": "```py\nx\n```!!", "score": 0.7},
        rank=2,
        max_chars=1800,
    )
    assert rc.score == 0.7 and rc.chunk.has_code
    assert rc.chunk.n_tokens == 4  # ceil(13 / 4)
    assert rc.chunk.doc_path == "web:/a"


def test_web_search_uses_original_question() -> None:
    h = _harness([])
    h.deps.web_search = FakeWebSearch([])
    out = nodes.web_search(_state(query="rewritten"), h.deps)
    assert h.deps.web_search.queries == [QUESTION]
    assert out["events"][1].data["outcome"] == "stop"


def test_generate_caps_contexts() -> None:
    h = _harness([], generator=[json.dumps({"answer": "a [1]", "cited": [1], "abstain": False})])
    web = [nodes.web_result_to_chunk(r, i, 1800) for i, r in enumerate(WEB_RESULTS * 2, 1)]
    out = nodes.generate(_state(relevant=chunks(1, 2, 3, 4, 5), web_docs=web), h.deps)
    assert len(out["contexts"]) == h.settings.final_k + h.settings.web_max_results


FAULT = "https://docs.langchain.com/oss/python/langgraph/fault-tolerance"
Q043_STYLE = [
    {"url": FAULT, "title": "Fault tolerance", "content": "plain"},
    {"url": FAULT + "#graph-defaults", "title": "Fault tolerance", "content": "fragment"},
    {"url": FAULT + "?ref=docs", "title": "Fault tolerance", "content": "query"},
]


def test_q043_style_duplicates_give_one_web_chunk() -> None:
    h = _harness([])
    h.deps.web_search = FakeWebSearch(Q043_STYLE)
    out = nodes.web_search(_state(diagnostics={"missing_grades": 0}), h.deps)
    assert [rc.chunk.url for rc in out["web_docs"]] == [FAULT]
    assert out["web_docs"][0].chunk.text == "plain"  # first occurrence kept
    assert out["diagnostics"] == {"missing_grades": 0, "web_duplicates_dropped": 2}
    event = out["events"][1]
    assert event.data["web_duplicates_dropped"] == 2 and event.data["n_results"] == 1


def test_dedupe_keeps_fragment_drops_query_and_ranks_are_contiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(nodes, "url_to_doc_ref", lambda url: seen.append(url))
    results = [
        {"url": FAULT + "?ref=docs#graph-defaults", "title": "a", "content": "1"},
        {"url": "https://DOCS.langchain.com/oss/python/langgraph/Fault-Tolerance/", "title": "b",
         "content": "dup"},
        {"url": "https://docs.langchain.com/oss/python/langgraph/persistence?x=1", "title": "c",
         "content": "2"},
        {"url": FAULT + "#other", "title": "d", "content": "dup"},
        {"url": "https://docs.langchain.com/oss/python/langgraph/interrupts", "title": "e",
         "content": "3"},
    ]  # fmt: skip
    h = _harness([])
    h.deps.web_search = FakeWebSearch(results)
    out = nodes.web_search(_state(), h.deps)
    urls = [rc.chunk.url for rc in out["web_docs"]]
    assert urls == [
        FAULT + "#graph-defaults",
        "https://docs.langchain.com/oss/python/langgraph/persistence",
        "https://docs.langchain.com/oss/python/langgraph/interrupts",
    ]
    assert seen == urls  # url_to_doc_ref gets the cleaned URL
    assert [rc.rank for rc in out["web_docs"]] == [1, 2, 3]
    assert out["diagnostics"]["web_duplicates_dropped"] == 2


def test_web_page_key() -> None:
    assert nodes.web_page_key("https://Docs.LangChain.com/A/b/?q=1#x") == "docs.langchain.com/a/b"
