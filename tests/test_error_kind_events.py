"""error_kind on the agentic error event and kind counting in the runner (M11 S1). No network."""

from pathlib import Path
from typing import Any

import groq
import httpx
from agentic_fakes import FakeRetriever, Harness, chunks
from eval_fakes import FakePipeline
from test_eval_runner import _run

from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import TraceEvent


def _json_validate_400() -> groq.BadRequestError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    body = {"error": {"type": "invalid_request_error", "code": "json_validate_failed"}}
    return groq.BadRequestError(
        "Error code: 400", response=httpx.Response(400, request=request), body=body
    )


def _error_event(error: Exception) -> TraceEvent:
    h = Harness(FakeRetriever(chunks(1), error=error), grader=[])
    events = list(h.pipeline.stream("q"))
    assert events[-1].type == "error"
    return events[-1]


def test_agentic_error_event_carries_error_kind() -> None:
    event = _error_event(_json_validate_400())
    assert event.message == "BadRequestError"  # message unchanged: class name only
    assert event.data == {"error_kind": "structured_output"}


def test_agentic_error_kind_unclassified_for_other_errors() -> None:
    event = _error_event(ValueError("prompt text and secret"))
    assert event.message == "ValueError"
    assert event.data == {"error_kind": "unclassified"}


class _KindPipeline(FakePipeline):
    """Fails each question once with an error event that carries error_kind."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__()
        self.kind, self.message, self.failed = kind, message, False

    def stream(self, question, run_metadata=None, callbacks=None):  # type: ignore[no-untyped-def]
        if question == "Q1?" and not self.failed:
            self.failed = True
            yield TraceEvent(type="node_start", node="generate", message="gen", t_ms=0)
            data: dict[str, Any] = {"error_kind": self.kind}
            yield TraceEvent(type="error", node="error", message=self.message, data=data, t_ms=1)
            return
        yield from super().stream(question, run_metadata, callbacks)


def _q001(tmp_path: Path) -> dict[str, Any]:
    return read_jsonl(tmp_path / "run" / "per_question.jsonl")[0]


def test_runner_counts_by_event_error_kind(tmp_path: Path) -> None:
    # A bare "BadRequestError" would be unclassified by message; the event's kind wins.
    _run(tmp_path, _KindPipeline("structured_output", "BadRequestError"))
    row = _q001(tmp_path)
    assert row["scores"]["structured_output_failures"] == 1
    assert row["scores"]["unclassified_call_errors"] == 0
    assert row["failed_attempts"][0]["kind"] == "structured_output"


def test_runner_counts_transient_separately(tmp_path: Path) -> None:
    _run(tmp_path, _KindPipeline("transient", "WebSearchError"))
    scores = _q001(tmp_path)["scores"]
    assert scores["structured_output_failures"] == 0
    assert scores["transient_call_errors"] == 1
    assert scores["rate_limited_attempts"] == 0


def test_runner_classifies_message_without_error_kind(tmp_path: Path) -> None:
    """An error event without error_kind (as from the baseline) is classified by message."""
    first = FakePipeline()
    first.fail_on = {"Q1?"}
    first.fail_message = "BadRequestError: 400"
    _run(tmp_path, first)
    _run(tmp_path, FakePipeline())
    row = _q001(tmp_path)
    assert row["scores"]["structured_output_failures"] == 0
    assert row["scores"]["unclassified_call_errors"] == 2
    assert {a["kind"] for a in row["failed_attempts"]} == {"unclassified"}
