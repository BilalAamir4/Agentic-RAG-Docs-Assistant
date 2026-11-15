"""Unit tests for ragdocs.tracing and baseline trace structure. No network access."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import langsmith.client
import langsmith.run_trees
import pytest
from langchain_core.runnables import RunnableLambda
from langsmith import run_helpers

from ragdocs.config import Settings, get_settings
from ragdocs.generation.answer import AnswerDraft
from ragdocs.pipelines.baseline import BaselinePipeline
from ragdocs.schemas import Chunk, RetrievedChunk
from ragdocs.tracing import configure_tracing, flush_traces, traced_run, tracing_enabled

FAKE_KEY = "lsv2_fake_key_never_logged_123"


class FakeClient:
    """Records the runs LangSmith would send, in place of langsmith.Client."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.updated: list[tuple[Any, dict[str, Any]]] = []

    def create_run(self, **kwargs: Any) -> None:
        """Record a posted run."""
        self.created.append(kwargs)

    def update_run(self, run_id: Any, **kwargs: Any) -> None:
        """Record a patched run."""
        self.updated.append((run_id, kwargs))


def _retrieved(chunk_id: str) -> RetrievedChunk:
    """Build a small RetrievedChunk."""
    chunk = Chunk(
        chunk_id=chunk_id,
        doc_path="d.mdx",
        url=f"https://docs.langchain.com/{chunk_id}",
        title="T",
        heading_path=[],
        anchor="a",
        text=f"text {chunk_id}",
        embed_text="e",
        n_tokens=2,
        has_code=False,
        source_commit="c",
    )
    return RetrievedChunk(chunk=chunk, score=0.7, rank=1, retriever="hybrid")


class _Retriever:
    mode = "hybrid"

    def retrieve(self, query: str, mode: str | None = None) -> list[RetrievedChunk]:
        return [_retrieved("chk-1")]


def _isolated_settings(**kwargs: Any) -> Settings:
    """Settings that ignore the repository .env file."""
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_configure_tracing_enabled_exports_env_and_hides_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Enabled with a key: env vars exported, real env values win, key never logged."""
    for name in ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", "already-set")
    caplog.set_level(logging.DEBUG)
    settings = _isolated_settings(
        langsmith_tracing=True, langsmith_api_key=FAKE_KEY, langsmith_project="ragdocs-local"
    )
    assert configure_tracing(settings) is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == FAKE_KEY
    assert os.environ["LANGSMITH_PROJECT"] == "already-set"
    assert tracing_enabled() is True
    assert FAKE_KEY not in caplog.text


def test_configure_tracing_missing_key_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Enabled without a key: one warning naming LANGSMITH_API_KEY, returns False."""
    caplog.set_level(logging.WARNING, logger="ragdocs.tracing")
    assert configure_tracing(_isolated_settings(langsmith_tracing=True)) is False
    warnings = [r for r in caplog.records if r.name == "ragdocs.tracing"]
    assert len(warnings) == 1
    assert "LANGSMITH_API_KEY" in warnings[0].getMessage()
    assert "LANGSMITH_API_KEY" not in os.environ


def test_configure_tracing_off_sets_false(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Disabled: tracing env var set to 'false', key not exported nor logged."""
    caplog.set_level(logging.DEBUG)
    settings = _isolated_settings(langsmith_tracing=False, langsmith_api_key=FAKE_KEY)
    assert configure_tracing(settings) is False
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert "LANGSMITH_API_KEY" not in os.environ
    assert tracing_enabled() is False
    assert FAKE_KEY not in caplog.text


def test_dotenv_enabling_tracing_is_overridden_in_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A .env with tracing on and a fake key still yields tracing off in normal tests."""
    (tmp_path / ".env").write_text(
        f"LANGSMITH_TRACING=true\nLANGSMITH_API_KEY={FAKE_KEY}\n", encoding="utf-8", newline="\n"
    )
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    assert configure_tracing(get_settings()) is False


def _forbid_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any LangSmith client construction fail loudly."""

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("LangSmith client must not be constructed")

    monkeypatch.setattr(langsmith.client.Client, "__init__", _boom)
    monkeypatch.setattr(langsmith.run_trees, "get_cached_client", _boom)


def test_traced_run_disabled_constructs_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled traced_run is a no-op and never builds a client."""
    _forbid_client(monkeypatch)
    with traced_run("baseline", "chain", {"question": "q"}, metadata={"a": 1}) as run:
        run.set_outputs({"answer": "x"})
        run.set_error("e")
    assert run.run_id is None
    flush_traces()


def test_baseline_stream_disabled_constructs_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """A full baseline run with tracing off builds no client."""
    _forbid_client(monkeypatch)
    llm = RunnableLambda(lambda msgs: AnswerDraft(answer="A [1].", cited=[1]))
    pipeline = BaselinePipeline(retriever=_Retriever(), structured_llm=llm)
    events = list(pipeline.stream("q", run_metadata={"run": "r1"}))
    assert [e.type for e in events][-1] == "answer"


def test_baseline_trace_structure_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enabled: one root 'baseline' run with nested hybrid_retrieve and generate runs."""
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
    fake = FakeClient()
    llm = RunnableLambda(lambda msgs: AnswerDraft(answer="A [1].", cited=[1]))
    pipeline = BaselinePipeline(retriever=_Retriever(), structured_llm=llm)
    with run_helpers.tracing_context(enabled=True, client=fake, project_name="test"):
        events = list(pipeline.stream("q", run_metadata={"run": "r1"}))
    assert events[-1].type == "answer"

    runs = {r["name"]: r for r in fake.created}
    root = runs["baseline"]
    assert root["run_type"] == "chain" and root.get("parent_run_id") is None
    assert root["extra"]["metadata"]["pipeline"] == "baseline"
    assert root["extra"]["metadata"]["run"] == "r1"
    assert runs["hybrid_retrieve"]["run_type"] == "retriever"
    assert runs["hybrid_retrieve"]["parent_run_id"] == root["id"]
    assert runs["generate"]["parent_run_id"] == root["id"]
    assert runs["generate"]["extra"]["metadata"]["run"] == "r1"

    patched = {str(rid): kw for rid, kw in fake.updated}
    docs = patched[str(runs["hybrid_retrieve"]["id"])]["outputs"]["documents"]
    assert docs[0]["type"] == "Document"
    assert docs[0]["page_content"] == "text chk-1"
    assert docs[0]["metadata"] == {
        "chunk_id": "chk-1",
        "url": "https://docs.langchain.com/chk-1",
        "rank": 1,
        "score": 0.7,
    }
    root_out = patched[str(root["id"])]["outputs"]
    assert root_out["n_citations"] == 1 and root_out["abstained"] is False


def test_tracing_module_import_boundary() -> None:
    """ragdocs.tracing imports nothing from ragdocs.eval, ragdocs.ingest or index.build."""
    script = "import json, sys\nimport ragdocs.tracing\nprint(json.dumps(sorted(sys.modules)))\n"
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    mods: list[str] = json.loads(result.stdout)
    ours = [m for m in mods if m.startswith("ragdocs")]
    assert set(ours) <= {"ragdocs", "ragdocs.config", "ragdocs.tracing"}, ours
