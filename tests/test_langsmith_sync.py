"""Tests for the LangSmith dataset sync and experiment replay with a fake client (no network)."""

import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from eval_fakes import FakeJudgeLLM, FakePipeline, make_settings
from test_eval_runner import _judge, _run

from ragdocs.eval.langsmith_sync import (
    EXPERIMENT_LOG,
    AlreadyUploaded,
    DatasetMismatch,
    build_payload,
    sync_dataset,
    upload_experiment,
)
from ragdocs.eval.runner import load_eval_items
from ragdocs.io_utils import read_json, write_jsonl

SHA = "a" * 64


class FakeClient:
    """In-memory stand-in for langsmith.Client (only the methods langsmith_sync uses)."""

    def __init__(self) -> None:
        self.datasets: dict[str, SimpleNamespace] = {}
        self.examples: dict[Any, list[SimpleNamespace]] = {}
        self.projects: list[SimpleNamespace] = []
        self.calls: list[str] = []

    def has_dataset(self, *, dataset_name: str) -> bool:
        return dataset_name in self.datasets

    def read_dataset(self, *, dataset_name: str) -> SimpleNamespace:
        return self.datasets[dataset_name]

    def create_dataset(self, name: str, *, description: str) -> SimpleNamespace:
        self.calls.append("create_dataset")
        ds = SimpleNamespace(id=uuid.uuid4(), name=name, description=description)
        self.datasets[name] = ds
        return ds

    def create_examples(self, *, dataset_id: Any, examples: list[dict]) -> None:
        self.calls.append("create_examples")
        self.examples.setdefault(dataset_id, []).extend(
            SimpleNamespace(inputs=e["inputs"], outputs=e["outputs"], metadata=e["metadata"])
            for e in examples
        )

    def list_examples(self, *, dataset_id: Any) -> list[SimpleNamespace]:
        return list(self.examples.get(dataset_id, []))

    def create_project(self, name: str, **kwargs: Any) -> SimpleNamespace:
        project = SimpleNamespace(
            id=uuid.uuid4(),
            name=name,
            url=f"https://ls.example/o/1/projects/p/{len(self.projects)}",
        )
        self.projects.append(project)
        return project


@pytest.fixture
def judged_run(tmp_path: Path) -> Path:
    _run(tmp_path, FakePipeline())
    _judge(tmp_path, FakeJudgeLLM())
    return tmp_path / "run"


def _items(tmp_path: Path):
    return load_eval_items(make_settings(tmp_path))


def test_dataset_sync_creates_once_and_verifies(tmp_path: Path) -> None:
    client, items = FakeClient(), _items(tmp_path)
    ds, created = sync_dataset(client, "ds", items, SHA)
    assert created and SHA in ds.description
    ex = client.list_examples(dataset_id=ds.id)
    assert [e.metadata["id"] for e in ex] == [i.id for i in items]
    assert ex[0].inputs == {"question": items[0].question}
    assert set(ex[0].metadata) == {"id", "category", "must_mention", "evidence"}
    ds2, created2 = sync_dataset(client, "ds", items, SHA)
    assert ds2 is ds and not created2
    assert client.calls == ["create_dataset", "create_examples"]  # no duplicates


def test_dataset_sync_stops_on_mismatch(tmp_path: Path) -> None:
    client, items = FakeClient(), _items(tmp_path)
    sync_dataset(client, "ds", items, SHA)
    with pytest.raises(DatasetMismatch, match="sha256"):
        sync_dataset(client, "ds", items, "b" * 64)
    with pytest.raises(DatasetMismatch, match="ids"):
        sync_dataset(client, "ds", items[:-1], SHA)


def test_payload_contains_every_stored_score(judged_run: Path) -> None:
    write_jsonl(
        judged_run / "ragas_scores.jsonl",
        [{"id": "q001", "category": "single", "faithfulness": 0.5, "response_relevancy": 0.9,
          "context_precision": None, "context_recall": 1.0,
          "errors": {"context_precision": "NaN"}}],
    )  # fmt: skip
    payload = build_payload(judged_run)
    assert sorted(payload) == ["q001", "q002", "q003", "q004"]
    fb = payload["q001"]["feedback"]
    assert set(fb) == {
        "correctness", "citation_support", "context_hit_at_5", "first_retrieval_hit_at_5",
        "context_evidence_recall_at_5",
        "must_mention_coverage", "llm_calls", "latency_ms", "tokens",
        "faithfulness", "response_relevancy", "context_recall",
    }  # fmt: skip
    assert fb["faithfulness"] == 0.5 and "context_precision" not in fb  # null omitted
    assert "abstention_correct" in payload["q004"]["feedback"]  # unanswerable item
    assert "hallucinated" in payload["q004"]["feedback"]
    assert (
        payload["q001"]["outputs"]["answer"]
        and "original_langsmith_run_id" in (payload["q001"]["metadata"])
    )


def test_experiment_replays_stored_values_and_logs_uploads(
    judged_run: Path, tmp_path: Path
) -> None:
    client, items = FakeClient(), _items(tmp_path)
    ds, _ = sync_dataset(client, "ds", items, SHA)
    captured: dict[str, Any] = {}

    def fake_evaluate(target, *, data, evaluators, experiment, **kwargs):
        captured["experiment"] = experiment.name
        captured["outputs"] = {e.metadata["id"]: target(e.inputs) for e in data}
        captured["scores"] = {e.metadata["id"]: evaluators[0](None, e) for e in data}

    entry = upload_experiment(client, judged_run, ds, evaluate_fn=fake_evaluate)
    assert entry["name"] == captured["experiment"] == "run"
    assert entry["url"].endswith(f"/datasets/{ds.id}/compare?selectedSessions={entry['id']}")
    payload = build_payload(judged_run)
    assert captured["outputs"]["q002"] == payload["q002"]["outputs"]
    keys = {r["key"] for r in captured["scores"]["q001"]["results"]}
    assert keys == set(payload["q001"]["feedback"])
    with pytest.raises(AlreadyUploaded):
        upload_experiment(client, judged_run, ds, evaluate_fn=fake_evaluate)
    second = upload_experiment(client, judged_run, ds, replace=True, evaluate_fn=fake_evaluate)
    assert second["name"] == "run-r1"
    log = read_json(judged_run / EXPERIMENT_LOG)["uploads"]
    assert [u["current"] for u in log] == [False, True]


def test_payload_counts_abstained_answerable_as_correctness_zero(judged_run: Path) -> None:
    """Same rule as the report: q003 (answerable, abstained, unjudged) gets correctness 0."""
    payload = build_payload(judged_run)
    assert payload["q003"]["feedback"]["correctness"] == 0.0
    assert "correctness" not in payload["q004"]["feedback"]  # unanswerable
