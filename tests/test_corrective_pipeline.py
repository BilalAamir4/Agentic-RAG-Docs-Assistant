"""AgenticPipeline streaming, errors, config, registry, Mermaid and report hooks (M10 S2)."""

import json
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from agentic_fakes import (
    FakeRetriever,
    Harness,
    answer,
    chunks,
    grades,
    rewrite,
)
from langchain_core.callbacks import BaseCallbackHandler

from ragdocs.config import REPO_ROOT
from ragdocs.eval.report import CONTEXTS_ARE_FIRST_RETRIEVAL, first_retrieval_hit_at_5
from ragdocs.io_utils import read_text
from ragdocs.pipelines import registry
from ragdocs.pipelines.agentic import pipeline as pipeline_module
from ragdocs.pipelines.agentic.graph import build_graph, export_mermaid
from ragdocs.pipelines.agentic.pipeline import RECURSION_LIMIT
from ragdocs.schemas import Evidence

NONE_RELEVANT = grades(False, False, False, False, False)


def _worst_case() -> Harness:
    return Harness(
        FakeRetriever(chunks(1, 2, 3, 4, 5), chunks(6, 7, 8, 9, 10)),
        grader=[NONE_RELEVANT, NONE_RELEVANT],
        rewriter=[rewrite("rewritten")],
        generator=[answer([1])],
    )


class ChatStartCounter(BaseCallbackHandler):
    """Counts chat-model starts it receives."""

    def __init__(self) -> None:
        self.starts: set[UUID] = set()

    def on_chat_model_start(
        self, serialized: Any, messages: Any, *, run_id: UUID, **_: Any
    ) -> None:
        self.starts.add(run_id)


def test_final_event_is_a_corrective_pipeline_result() -> None:
    events, result = _worst_case().run()
    assert events[-1].node == "answer"
    assert result.pipeline == "corrective"
    assert sum(1 for e in events if e.type == "answer") == 1


def test_callbacks_reach_every_llm_call() -> None:
    handler = ChatStartCounter()
    _, result = _worst_case().run(callbacks=[handler])
    assert result.llm_calls == 4
    assert len(handler.starts) == 4


def test_t_ms_non_decreasing_and_trace_matches_yield_order() -> None:
    events, result = _worst_case().run()
    # As in BaselinePipeline, the trace holds every yielded event, the answer event last.
    assert len(result.trace) == len(events)
    for got, yielded in zip(result.trace, events, strict=True):
        assert (got.type, got.node, got.message, got.t_ms) == (
            yielded.type, yielded.node, yielded.message, yielded.t_ms,
        )  # fmt: skip
    for got, yielded in zip(result.trace[:-1], events[:-1], strict=True):
        assert got.model_dump() == yielded.model_dump()
    assert result.trace[-1].type == "answer"
    stamps = [e.t_ms for e in events]
    assert stamps == sorted(stamps)
    assert result.latency_ms <= events[-1].t_ms


def test_trace_shape_matches_baseline_answer_event() -> None:
    events, result = _worst_case().run()
    inner = result.trace[-1].data  # dumped before the answer event was appended
    assert [e["type"] for e in inner["trace"]] == [e.type for e in events[:-1]]


def test_node_exception_yields_exactly_one_error_event() -> None:
    h = Harness(FakeRetriever(chunks(1), error=ValueError("prompt text and secret")), grader=[])
    events = list(h.pipeline.stream("q"))
    errors = [e for e in events if e.type == "error"]
    assert len(errors) == 1 and events[-1] is errors[0]
    assert errors[0].message == "ValueError"
    assert not any(e.type == "answer" for e in events)


def test_recursion_limit_error_yields_one_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    h = _worst_case()
    monkeypatch.setattr(pipeline_module, "RECURSION_LIMIT", 3)
    events = list(h.pipeline.stream("q"))
    assert [e.type for e in events].count("error") == 1
    assert events[-1].type == "error" and events[-1].message == "GraphRecursionError"


def test_recursion_limit_20_is_passed_to_the_graph() -> None:
    h = _worst_case()
    seen: dict[str, Any] = {}
    real_graph = h.pipeline.graph

    class Spy:
        def stream(self, state: Any, config: dict[str, Any], **kw: Any) -> Any:
            seen.update(config)
            return real_graph.stream(state, config, **kw)

    h.pipeline.graph = Spy()
    h.run()
    assert RECURSION_LIMIT == 20
    assert seen["recursion_limit"] == 20
    assert seen["run_name"] == "graph"
    assert seen["metadata"]["pipeline"] == "corrective"


def test_self_rag_builds() -> None:
    graph = build_graph("self_rag", _worst_case().deps)
    names = set(graph.get_graph().nodes)
    for node in ("decide_retrieval", "out_of_scope", "verify_answer", "regenerate", "abstain"):
        assert node in names


def test_committed_mermaid_matches_fresh_export() -> None:
    committed = read_text(REPO_ROOT / "docs" / "graphs" / "corrective.mmd")
    assert committed == export_mermaid("corrective")
    for edge in ("retrieve --> grade_documents", "rewrite_query --> retrieve",
                 "web_search --> generate", "grade_documents -.-> web_search"):  # fmt: skip
        assert edge in committed


def test_first_retrieval_hit_uses_corrective_trace_chunk_ids() -> None:
    # First retrieval c1..c5 all judged irrelevant; contexts come from the second one.
    h = Harness(
        FakeRetriever(chunks(1, 2, 3, 4, 5), chunks(6, 7, 8, 9, 10)),
        grader=[NONE_RELEVANT, grades(True, False, False, False, False)],
        rewriter=[rewrite("rewritten")],
        generator=[answer([1])],
    )
    _, result = h.run()
    assert "corrective" not in CONTEXTS_ARE_FIRST_RETRIEVAL
    assert [c.chunk.chunk_id for c in result.contexts] == ["c6"]
    gold = Evidence(doc_path="gold.mdx", anchor="g")
    refs = {"c3": gold, "c6": Evidence(doc_path="other.mdx", anchor="o")}
    record = SimpleNamespace(result=result, evidence=[gold])
    assert first_retrieval_hit_at_5(record, refs) == 1.0
    # Resolved by chunk_id, not URL: without the c3 mapping (and URLs off-corpus) it misses.
    assert first_retrieval_hit_at_5(record, {"c6": gold}) == 0.0


def test_corrective_is_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    assert registry.list_pipelines() == ["baseline", "corrective", "self_rag"]
    deps = _worst_case().deps
    monkeypatch.setattr(pipeline_module, "build_default_deps", lambda: deps)
    registry.clear_pipeline_cache()
    try:
        p = registry.get_pipeline("corrective")
        assert p.name == "corrective" and p.deps is deps
    finally:
        registry.clear_pipeline_cache()


@pytest.mark.parametrize(
    "module",
    [
        "ragdocs.pipelines.agentic",
        "ragdocs.pipelines.agentic.pipeline",
        "ragdocs.pipelines.agentic.graph",
        "ragdocs.pipelines.agentic.nodes",
        "ragdocs.pipelines.registry",
    ],
)
def test_agentic_modules_are_runtime_safe(module: str) -> None:
    script = f"import json, sys\nimport {module}\nprint(json.dumps(sorted(sys.modules.keys())))\n"
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    modules: list[str] = json.loads(result.stdout)
    forbidden = ("ragdocs.eval", "ragdocs.ingest", "ragdocs.index.build", "ragas")
    assert not any(m.startswith(forbidden) for m in modules)
