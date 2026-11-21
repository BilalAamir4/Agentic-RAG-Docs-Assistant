"""Self-RAG graph paths, the 8-call bound, D26 fallbacks and decision outcomes (M11 S2).

Fakes only (tests/self_rag_fakes.py); no network. Letters in test docstrings refer to
the S2 module prompt's test list.
"""

from pathlib import Path
from typing import Any

import pytest
from agentic_fakes import WEB_RESULTS, FakeRetriever, answer, chunks, grades, rewrite
from langchain_core.messages import HumanMessage
from self_rag_fakes import (
    MALFORMED,
    SelfRagHarness,
    connection_error,
    decide,
    json_validate_failed,
    rate_limit_error,
    verify,
)
from test_failure_kinds import _edit_rows, run_dir  # noqa: F401  (pytest fixture)

import ragdocs.eval.report as report
from ragdocs.eval.report import format_cell, summarize
from ragdocs.generation.answer import format_context
from ragdocs.generation.prompts import ABSTAIN_TEXT, ANSWER_USER_TEMPLATE
from ragdocs.pipelines.agentic import pipeline as pipeline_module
from ragdocs.pipelines.agentic.graph import build_graph
from ragdocs.pipelines.agentic.pipeline import RECURSION_LIMIT
from ragdocs.pipelines.agentic.prompts import (
    OUT_OF_SCOPE_TEXT,
    VERIFY_SYSTEM_PROMPT,
    VERIFY_USER_TEMPLATE,
)
from ragdocs.pipelines.agentic.state import OUTCOMES
from ragdocs.schemas import PipelineResult, TraceEvent

ALL_RELEVANT = grades(True, True, True, True, True)
NONE_RELEVANT = grades(False, False, False, False, False)
SELF_RAG_NODES = ("decide_retrieval", "out_of_scope", "verify_answer", "regenerate", "abstain")
CLAIMS = ["MemorySaver persists to disk", "compile takes a store argument"]


def _simple(verifier: list[Any], generator: list[Any] | None = None) -> SelfRagHarness:
    """decide true, all 5 chunks relevant, one generation, scripted verifier."""
    return SelfRagHarness(
        FakeRetriever(chunks(1, 2, 3, 4, 5)),
        decider=[decide(True)],
        grader=[ALL_RELEVANT],
        verifier=verifier,
        generator=generator or [answer([1])],
    )


def _worst_case(**kw: Any) -> SelfRagHarness:
    """decide, grade, rewrite, grade, (web) generate, verify, regenerate, verify, abstain."""
    return SelfRagHarness(
        FakeRetriever(chunks(1, 2, 3, 4, 5), chunks(6, 7, 8, 9, 10)),
        decider=[decide(True)],
        grader=[NONE_RELEVANT, NONE_RELEVANT],
        rewriter=[rewrite("checkpointer compile")],
        web=WEB_RESULTS,
        generator=[answer([1]), answer([1])],
        verifier=[verify(False, CLAIMS), verify(False, CLAIMS[:1])],
        **kw,
    )


def path(events: list[TraceEvent]) -> list[str]:
    """Node names in node_start order."""
    return [e.node for e in events if e.type == "node_start"]


def new_outcomes(events: list[TraceEvent]) -> list[tuple[str, str]]:
    """(node, outcome) of every decision event of the self_rag nodes, in order."""
    return [
        (e.node, e.data["outcome"])
        for e in events
        if e.type == "decision" and e.node in SELF_RAG_NODES
    ]


def decision_of(events: list[TraceEvent], node: str, index: int = 0) -> TraceEvent:
    """The index-th decision event of node."""
    return [e for e in events if e.type == "decision" and e.node == node][index]


def assert_common(h: SelfRagHarness, events: list[TraceEvent], result: PipelineResult) -> None:
    """(o) and (n): final event parses, t_ms ordered, contexts are the generator's chunks."""
    assert events[-1].type == "answer"
    PipelineResult.model_validate(events[-1].data)
    stamps = [e.t_ms for e in events]
    assert stamps == sorted(stamps)
    assert all(e.data["outcome"] in OUTCOMES for e in events if e.type == "decision")
    assert result.pipeline == "self_rag"
    if not h.generator.received:
        assert result.contexts == []
        return
    expected = ANSWER_USER_TEMPLATE.format(
        question=result.question, context=format_context(result.contexts)
    )
    for messages in h.generator.received:
        assert messages[1].content == expected
    assert result.llm_calls == sum(h.calls().values())


# (a) to (g): routing paths


def test_a_off_topic_goes_out_of_scope_with_one_call() -> None:
    h = SelfRagHarness(FakeRetriever(chunks(1)), decider=[decide(False, "a greeting")])
    events, result = h.run("hi, what can you do?")
    assert path(events) == ["decide_retrieval", "out_of_scope"]
    assert result.llm_calls == 1
    assert result.contexts == []
    assert result.answer.abstained and result.answer.text == OUT_OF_SCOPE_TEXT
    assert result.answer.citations == []
    assert not any(e.type == "retrieval" for e in events)
    assert h.retriever.queries == []
    assert new_outcomes(events) == [("decide_retrieval", "stop"), ("out_of_scope", "stop")]
    d = decision_of(events, "decide_retrieval")
    assert d.data["needs_docs"] is False and d.data["reason"] == "a greeting"
    assert_common(h, events, result)


def test_b_grounded_and_answering_ends_after_first_verify() -> None:
    h = _simple([verify(True)])
    events, result = h.run()
    assert path(events) == ["decide_retrieval", "retrieve", "grade_documents", "generate",
                            "verify_answer"]  # fmt: skip
    assert result.llm_calls == 4
    assert not result.answer.abstained
    assert new_outcomes(events) == [("decide_retrieval", "ok"), ("verify_answer", "ok")]
    v = decision_of(events, "verify_answer")
    assert v.data["grounded"] is True and v.data["answers_question"] is True
    assert v.data["unsupported_claims"] == [] and v.data["regenerations"] == 0
    assert result.diagnostics.get("fallbacks", []) == []
    assert_common(h, events, result)


def test_verify_call_sees_question_contexts_and_answer() -> None:
    h = _simple([verify(True)])
    _, result = h.run()
    messages = h.verifier.received[0]
    assert messages[0].content == VERIFY_SYSTEM_PROMPT
    assert messages[1].content == VERIFY_USER_TEMPLATE.format(
        question=result.question, context=format_context(result.contexts), answer=result.answer.text
    )


def test_c_ungrounded_then_grounded_after_one_regeneration() -> None:
    h = _simple([verify(False, CLAIMS), verify(True)], generator=[answer([1]), answer([2])])
    events, result = h.run()
    assert path(events)[-3:] == ["verify_answer", "regenerate", "verify_answer"]
    assert not result.answer.abstained
    assert [c.chunk_id for c in result.answer.citations] == ["c2"]  # the regenerated answer
    assert new_outcomes(events) == [
        ("decide_retrieval", "ok"), ("verify_answer", "retry"), ("regenerate", "retry"),
        ("verify_answer", "ok"),
    ]  # fmt: skip
    first, second = h.generator.received
    assert first[:2] == second[:2]  # same shared prompt and contexts
    assert len(second) == len(first) + 1
    extra = second[2]
    assert isinstance(extra, HumanMessage)
    for claim in CLAIMS:
        assert f"- {claim}\n" in extra.content
    assert decision_of(events, "regenerate").data["claims"] == CLAIMS
    assert decision_of(events, "verify_answer", 1).data["regenerations"] == 1
    assert_common(h, events, result)


def test_regenerate_with_no_listed_claims_uses_placeholder_line() -> None:
    h = _simple([verify(False, []), verify(True)], generator=[answer([1]), answer([1])])
    h.run()
    extra = h.generator.received[1][2].content
    assert "\n- (the checker listed no specific claims)\n" in extra


def test_d_ungrounded_twice_abstains_not_grounded() -> None:
    h = _simple([verify(False, CLAIMS), verify(False, CLAIMS)], generator=[answer(), answer()])
    events, result = h.run()
    assert path(events)[-4:] == ["verify_answer", "regenerate", "verify_answer", "abstain"]
    assert result.answer.abstained and result.answer.text == ABSTAIN_TEXT
    assert result.diagnostics["abstain_reason"] == "not_grounded"
    assert new_outcomes(events)[-2:] == [("verify_answer", "stop"), ("abstain", "stop")]
    assert decision_of(events, "abstain").data["abstain_reason"] == "not_grounded"
    assert len(result.contexts) == 5  # contexts unchanged by abstain
    assert_common(h, events, result)


def test_e_grounded_but_not_answering_abstains_without_second_retrieval() -> None:
    h = _simple([verify(True, answers=False)])
    events, result = h.run()
    assert path(events).count("retrieve") == 1
    assert "regenerate" not in path(events)
    assert result.answer.abstained
    assert result.diagnostics["abstain_reason"] == "does_not_answer"
    assert new_outcomes(events) == [("decide_retrieval", "ok"), ("verify_answer", "stop"),
                                    ("abstain", "stop")]  # fmt: skip
    assert len(h.retriever.queries) == 1
    assert_common(h, events, result)


def test_f_abstained_generation_skips_verification() -> None:
    h = _simple([], generator=[answer(abstain=True)])
    events, result = h.run()
    assert h.verifier.received == []
    v = decision_of(events, "verify_answer")
    assert v.message == "verification skipped: abstained" and v.data["outcome"] == "info"
    assert result.answer.abstained
    assert path(events)[-1] == "verify_answer"
    assert_common(h, events, result)


def test_f_no_contexts_abstains_in_generate_and_skips_verification() -> None:
    h = SelfRagHarness(
        FakeRetriever(chunks(1, 2, 3, 4, 5)),
        decider=[decide(True)],
        grader=[NONE_RELEVANT, NONE_RELEVANT],
        rewriter=[rewrite("other")],
        web=[],
    )
    events, result = h.run()
    assert h.verifier.received == [] and h.generator.received == []
    assert result.contexts == [] and result.answer.abstained
    assert decision_of(events, "verify_answer").data["outcome"] == "info"
    assert_common(h, events, result)


def test_g_worst_case_is_exactly_eight_calls_within_recursion_limit() -> None:
    h = _worst_case()
    events, result = h.run()
    assert path(events) == [
        "decide_retrieval", "retrieve", "grade_documents", "rewrite_query", "retrieve",
        "grade_documents", "web_search", "generate", "verify_answer", "regenerate",
        "verify_answer", "abstain",
    ]  # fmt: skip
    assert result.llm_calls == 8
    assert h.calls() == {"decide": 1, "grade": 2, "rewrite": 1, "generate": 2, "verify": 2}
    assert RECURSION_LIMIT == 20 and len(path(events)) == 12 < RECURSION_LIMIT
    assert result.answer.abstained and result.used_web
    assert result.diagnostics["abstain_reason"] == "not_grounded"
    assert new_outcomes(events) == [
        ("decide_retrieval", "ok"), ("verify_answer", "retry"), ("regenerate", "retry"),
        ("verify_answer", "stop"), ("abstain", "stop"),
    ]  # fmt: skip
    assert_common(h, events, result)


def test_g_worst_case_fails_below_its_step_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """12 node steps need a limit of 13 (measured in S2); 20 leaves 7 spare."""
    monkeypatch.setattr(pipeline_module, "RECURSION_LIMIT", 13)
    assert _worst_case().stream()[-1].type == "answer"
    monkeypatch.setattr(pipeline_module, "RECURSION_LIMIT", 12)
    assert _worst_case().stream()[-1].message == "GraphRecursionError"


# (h) to (m): D26 fallbacks and propagated errors


def test_h_decide_failed_retrieves_by_default() -> None:
    h = _simple([verify(True)])
    h.decider.responses = [MALFORMED]
    events, result = h.run()
    assert path(events)[:2] == ["decide_retrieval", "retrieve"]
    d = decision_of(events, "decide_retrieval")
    assert d.message == "retrieval decision failed; retrieving by default"
    assert d.data["outcome"] == "info" and d.data["needs_docs"] is True
    assert d.data["fallback"] == "decide_failed"
    assert d.data["error_kind"] == "structured_output"
    assert result.diagnostics["fallbacks"] == ["decide_failed"]
    assert not result.answer.abstained
    assert_common(h, events, result)


def test_h_decide_json_validate_failed_400_is_a_fallback() -> None:
    h = _simple([verify(True)])
    h.decider.responses = [json_validate_failed()]
    events, result = h.run()
    assert decision_of(events, "decide_retrieval").data["error_kind"] == "structured_output"
    assert result.diagnostics["fallbacks"] == ["decide_failed"]


def test_i_verify_failed_on_first_verify_keeps_answer() -> None:
    h = _simple([MALFORMED])
    events, result = h.run()
    assert "regenerate" not in path(events)
    assert len(h.generator.received) == 1
    assert not result.answer.abstained
    v = decision_of(events, "verify_answer")
    assert v.message == "verification failed; answer kept unchecked"
    assert v.data["outcome"] == "info" and v.data["fallback"] == "verify_failed"
    assert v.data["error_kind"] == "structured_output"
    assert result.diagnostics["fallbacks"] == ["verify_failed"]
    assert "abstain_reason" not in result.diagnostics
    assert_common(h, events, result)


def test_j_verify_failed_on_second_verify_keeps_regenerated_answer() -> None:
    h = _simple([verify(False, CLAIMS), MALFORMED], generator=[answer([1]), answer([3])])
    events, result = h.run()
    assert path(events)[-3:] == ["verify_answer", "regenerate", "verify_answer"]
    assert [c.chunk_id for c in result.answer.citations] == ["c3"]
    assert not result.answer.abstained
    assert new_outcomes(events)[-1] == ("verify_answer", "info")
    assert result.diagnostics["fallbacks"] == ["verify_failed"]
    assert_common(h, events, result)


def test_k_regenerate_failed_abstains() -> None:
    h = _simple([verify(False, CLAIMS)], generator=[answer([1]), MALFORMED])
    events, result = h.run()
    assert path(events)[-3:] == ["verify_answer", "regenerate", "abstain"]
    r = decision_of(events, "regenerate")
    assert r.data["outcome"] == "stop" and r.data["fallback"] == "regenerate_failed"
    assert r.data["error_kind"] == "structured_output"
    assert result.answer.abstained and result.answer.text == ABSTAIN_TEXT
    assert result.diagnostics["abstain_reason"] == "regenerate_failed"
    assert result.diagnostics["fallbacks"] == ["regenerate_failed"]
    assert decision_of(events, "abstain").data["abstain_reason"] == "regenerate_failed"
    assert len(h.verifier.received) == 1
    assert_common(h, events, result)


@pytest.mark.parametrize("node", ["decide", "verify"])
@pytest.mark.parametrize(
    ("make_error", "kind", "name"),
    [
        (rate_limit_error, "rate_limit", "RateLimitError"),
        (connection_error, "transient", "APIConnectionError"),
    ],  # fmt: skip
)
def test_l_non_structured_errors_yield_one_error_event(
    node: str, make_error: Any, kind: str, name: str
) -> None:
    h = _simple([verify(True)])
    model = h.decider if node == "decide" else h.verifier
    model.responses = [make_error()]
    events = h.stream()
    errors = [e for e in events if e.type == "error"]
    assert len(errors) == 1 and events[-1] is errors[0]
    assert errors[0].message == name and errors[0].data == {"error_kind": kind}
    assert not any(e.type == "answer" for e in events)
    assert not any("fallback" in e.data for e in events)


def test_m_fallbacks_survive_later_nodes_and_accumulate() -> None:
    h = _simple([MALFORMED])
    h.decider.responses = [MALFORMED]
    events, result = h.run()
    assert result.diagnostics["fallbacks"] == ["decide_failed", "verify_failed"]
    # Keys written by corrective nodes in between are kept too.
    for key in ("missing_grades", "invalid_grades", "grading_failures"):
        assert key in result.diagnostics
    assert_common(h, events, result)


def test_m_decide_and_regenerate_fallbacks_both_listed() -> None:
    h = _simple([verify(False, CLAIMS)], generator=[answer([1]), MALFORMED])
    h.decider.responses = [MALFORMED]
    _, result = h.run()
    assert result.diagnostics["fallbacks"] == ["decide_failed", "regenerate_failed"]
    assert result.diagnostics["abstain_reason"] == "regenerate_failed"


# (p) report counting


def test_p_report_counts_self_rag_fallbacks_not_structured_failures(
    run_dir: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The fake chunks c1..c10 are not in an index; resolve none of them (all misses).
    monkeypatch.setattr(report, "chunk_refs", lambda index_dir=None: {})
    two_fallbacks = _simple([MALFORMED])  # decide_failed and verify_failed on one item
    two_fallbacks.decider.responses = [MALFORMED]
    results = {
        "q001": two_fallbacks.run()[1].model_dump(mode="json"),
        "q002": _worst_case().run()[1].model_dump(mode="json"),  # no fallback
    }

    def edit(row: dict[str, Any]) -> None:
        if row["id"] in results:
            row["result"] = results[row["id"]]

    _edit_rows(run_dir, edit)
    o = summarize(run_dir)["overall"]
    assert o["structured_call_fallbacks"]["count"] == 1
    assert format_cell(o, "structured_call_fallbacks", "fallbacks").endswith(
        "decide_failed 1, verify_failed 1, regenerate_failed 0"
    )
    assert o["structured_output_failures"]["total"] == 0
    assert o["items_with_structured_output_failures"]["count"] == 0


# (q) corrective unchanged


def test_q_corrective_graph_has_no_self_rag_nodes() -> None:
    deps = _simple([]).deps
    names = set(build_graph("corrective", deps).get_graph().nodes)
    assert not names & set(SELF_RAG_NODES)
    assert set(SELF_RAG_NODES) <= set(build_graph("self_rag", deps).get_graph().nodes)


def test_self_rag_mermaid_has_no_edge_back_to_retrieval() -> None:
    from ragdocs.config import REPO_ROOT
    from ragdocs.io_utils import read_text
    from ragdocs.pipelines.agentic.graph import export_mermaid

    committed = read_text(REPO_ROOT / "docs" / "graphs" / "self_rag.mmd")
    assert committed == export_mermaid("self_rag")
    for src in ("verify_answer", "regenerate"):
        for dest in ("retrieve", "rewrite_query", "grade_documents", "decide_retrieval"):
            assert f"{src} --> {dest};" not in committed
            assert f"{src} -.-> {dest};" not in committed
    for edge in ("__start__ --> decide_retrieval;", "generate --> verify_answer;",
                 "verify_answer -.-> regenerate;", "regenerate -.-> verify_answer;",
                 "verify_answer -.-> __end__;", "out_of_scope --> __end__;"):  # fmt: skip
        assert edge in committed


def test_corrective_results_carry_no_diagnostics_key() -> None:
    from agentic_fakes import Harness

    h = Harness(FakeRetriever(chunks(1, 2, 3, 4, 5)), grader=[ALL_RELEVANT],
                generator=[answer([1])])  # fmt: skip
    events, result = h.run()
    assert result.diagnostics == {}
    assert "diagnostics" not in events[-1].data


def test_self_rag_is_registered_and_traced_as_self_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager

    from ragdocs.pipelines import registry

    h = _simple([verify(True)])
    monkeypatch.setattr(pipeline_module, "build_default_deps", lambda: h.deps)
    registry.clear_pipeline_cache()
    names: list[str] = []
    real = pipeline_module.traced_run

    @contextmanager
    def spy(name: str, **kw: Any) -> Any:
        names.append(name)
        with real(name=name, **kw) as run:
            yield run

    monkeypatch.setattr(pipeline_module, "traced_run", spy)
    try:
        p = registry.get_pipeline("self_rag")
        assert p.name == "self_rag" and p.deps is h.deps
        seen: dict[str, Any] = {}
        real_graph = p.graph

        class Spy:
            def stream(self, state: Any, config: dict[str, Any], **kw: Any) -> Any:
                seen.update(config)
                return real_graph.stream(state, config, **kw)

        p.graph = Spy()
        list(p.stream("q"))
        assert names == ["self_rag"]
        assert seen["run_name"] == "graph" and seen["recursion_limit"] == 20
    finally:
        registry.clear_pipeline_cache()


def test_self_rag_nodes_module_is_runtime_safe() -> None:
    import json
    import subprocess
    import sys

    module = "ragdocs.pipelines.agentic.self_rag_nodes"
    script = f"import json, sys\nimport {module}\nprint(json.dumps(sorted(sys.modules.keys())))\n"
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    forbidden = ("ragdocs.eval", "ragdocs.ingest", "ragdocs.index.build", "ragas")
    assert not any(m.startswith(forbidden) for m in json.loads(out.stdout))
