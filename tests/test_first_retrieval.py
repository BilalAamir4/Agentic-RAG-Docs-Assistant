"""Tests for first_retrieval_hit@5 (M10, D22): synthetic traces and the committed baseline run.

No network: the LangSmith client and evaluate are fakes, and the baseline run folder is
copied to tmp_path before any upload so committed files are never written.
"""

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from eval_fakes import make_chunk
from test_langsmith_sync import FakeClient

from ragdocs.config import REPO_ROOT
from ragdocs.eval.judge import load_records
from ragdocs.eval.langsmith_sync import (
    build_payload,
    read_log,
    sync_dataset,
    upload_experiment,
)
from ragdocs.eval.report import first_retrieval_hit_at_5, summarize
from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import Answer, EvalItem, Evidence, PipelineResult, TraceEvent

BASELINE_RUN = REPO_ROOT / "results" / "runs" / "baseline-20261116-1050"
GOLD = [Evidence(doc_path="add-memory.mdx", anchor="add-short-term-memory")]
GOLD_URL = "https://docs.langchain.com/oss/python/langgraph/add-memory#add-short-term-memory"
OTHER_URL = "https://docs.langchain.com/oss/python/langgraph/add-memory"
REFS = {
    "gold": GOLD[0],
    "other": Evidence(doc_path="add-memory.mdx", anchor=""),
}


def _record(chunks: list[dict[str, Any]] | None, pipeline: str = "corrective") -> Any:
    """Answerable record whose trace has one retrieval event (none when chunks is None)."""
    trace = [TraceEvent(type="node_start", node="retrieve", message="", t_ms=0)]
    if chunks is not None:
        trace.append(
            TraceEvent(
                type="retrieval", node="retrieve", message="", data={"chunks": chunks}, t_ms=1
            )
        )
    result = PipelineResult(
        question="q",
        pipeline=pipeline,
        answer=Answer(text="a", citations=[], abstained=False),
        contexts=[make_chunk(1)],
        trace=trace,
        llm_calls=1,
        latency_ms=1,
    )
    return SimpleNamespace(result=result, evidence=GOLD)


def test_hit_in_top_5() -> None:
    chunks = [{"chunk_id": "other", "url": OTHER_URL}] * 4 + [{"chunk_id": "gold", "url": GOLD_URL}]
    assert first_retrieval_hit_at_5(_record(chunks), REFS) == 1.0


def test_miss_when_gold_is_ranked_sixth() -> None:
    chunks = [{"chunk_id": "other", "url": OTHER_URL}] * 5 + [{"chunk_id": "gold", "url": GOLD_URL}]
    assert first_retrieval_hit_at_5(_record(chunks), REFS) == 0.0


def test_no_retrieval_event_is_a_miss() -> None:
    assert first_retrieval_hit_at_5(_record(None), REFS) == 0.0


def test_only_the_first_retrieval_event_counts() -> None:
    record = _record([{"chunk_id": "other", "url": OTHER_URL}])
    record.result.trace.append(
        TraceEvent(type="retrieval", node="retrieve", message="",
                   data={"chunks": [{"chunk_id": "gold", "url": GOLD_URL}]}, t_ms=2)
    )  # fmt: skip
    assert first_retrieval_hit_at_5(record, REFS) == 0.0


def test_chunk_id_lookup_preferred_over_url() -> None:
    # chunk_id says "other"; the URL alone would match the gold evidence.
    assert first_retrieval_hit_at_5(_record([{"chunk_id": "other", "url": GOLD_URL}]), REFS) == 0.0
    # and the reverse: chunk_id resolves to gold although the URL does not.
    assert first_retrieval_hit_at_5(_record([{"chunk_id": "gold", "url": OTHER_URL}]), REFS) == 1.0


def test_url_fallback_for_web_chunk_id() -> None:
    web = [{"chunk_id": "web-0", "url": GOLD_URL}]
    assert first_retrieval_hit_at_5(_record(web), REFS) == 1.0
    off = [{"chunk_id": "web-1", "url": "https://example.com/add-memory#add-short-term-memory"}]
    assert first_retrieval_hit_at_5(_record(off), REFS) == 0.0


def test_baseline_uses_contexts() -> None:
    record = _record(None, pipeline="baseline")
    record.evidence = [Evidence(doc_path="doc.mdx", anchor="a1")]  # make_chunk(1)
    assert first_retrieval_hit_at_5(record, REFS) == 1.0


def test_baseline_run_first_retrieval_equals_context_hit_per_item() -> None:
    records = [r for r in load_records(BASELINE_RUN) if r.category != "unanswerable"]
    assert len(records) == 42
    for r in records:
        assert first_retrieval_hit_at_5(r) == r.scores.context_hit_at_5, r.id
        # The URL path (no chunk_id in the baseline event) gives the same value.
        url_only = r.model_copy(deep=True)
        url_only.result.pipeline = "url-only-check"
        assert first_retrieval_hit_at_5(url_only) == r.scores.context_hit_at_5, r.id
    s = summarize(BASELINE_RUN)
    assert s["overall"]["first_retrieval_hit@5"] == s["overall"]["context_hit@5"]
    for cat, per in s["per_category"].items():
        assert per["first_retrieval_hit@5"] == per["context_hit@5"], cat


def test_baseline_experiment_payload_carries_first_retrieval_hit(tmp_path: Path) -> None:
    run = tmp_path / BASELINE_RUN.name
    shutil.copytree(BASELINE_RUN, run)
    payload = build_payload(run)
    for r in load_records(run):
        fb = payload[r.id]["feedback"]
        if r.category == "unanswerable":
            assert "first_retrieval_hit_at_5" not in fb
        else:
            assert fb["first_retrieval_hit_at_5"] == fb["context_hit_at_5"]
    items = [EvalItem(**row) for row in read_jsonl(REPO_ROOT / "data" / "eval" / "eval_set.jsonl")]
    client = FakeClient()
    ds, _ = sync_dataset(client, "ds", items, "a" * 64)
    captured: dict[str, Any] = {}

    def fake_evaluate(target: Any, *, data: Any, evaluators: Any, **kwargs: Any) -> None:
        captured.update({e.metadata["id"]: evaluators[0](None, e) for e in data})

    n_logged = len(read_log(run)["uploads"])  # copied log; the committed one is untouched
    entry = upload_experiment(client, run, ds, replace=True, evaluate_fn=fake_evaluate)
    assert entry["name"] == f"{BASELINE_RUN.name}-r{n_logged}"
    keys = {res["key"] for res in captured["q001"]["results"]}
    assert {"first_retrieval_hit_at_5", "context_hit_at_5"} <= keys
