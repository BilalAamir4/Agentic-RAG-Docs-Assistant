"""Failed-attempt kinds, overrides and structured-call fallbacks in the report (M11 S1).

Run folders are built with the fake runner in tmp_path, then their per_question.jsonl
lines are edited by hand to hold the failed attempts and diagnostics under test.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from eval_fakes import FakePipeline, make_settings
from test_eval_runner import _run

import ragdocs.eval.report as report
from ragdocs.eval.compare import render_comparison
from ragdocs.eval.failures import attempt_kind, item_kinds, load_overrides
from ragdocs.eval.report import format_cell, render_markdown, summarize
from ragdocs.io_utils import read_jsonl, write_json, write_jsonl
from ragdocs.schemas import ErrorReclassification, FailedAttempt, PipelineResult

JSON_400 = (
    "BadRequestError: Error code: 400 - {'error': {'type': 'invalid_request_error', "
    "'code': 'json_validate_failed'}}"
)
# (message, expected kind) for each kind, as stored by older runs (no kind field).
MESSAGES = [
    ("RateLimitError: Error code: 429 - {'error': {}}", "rate_limit"),
    (JSON_400, "structured_output"),
    ("OutputParserException", "structured_output"),
    ("APIConnectionError: Connection error.", "transient"),
    ("AuthenticationError: Error code: 401", "permanent"),
    ("BadRequestError: 400", "unclassified"),
    ("WebSearchError", "unclassified"),
    ("NeverSeenBeforeError: something", "unclassified"),
]
UTC = "2026-11-21T00:00:00+00:00"


def _attempt(message: str, kind: str | None = None, utc: str = UTC) -> dict[str, Any]:
    return {"stage": "generate", "message": message, "utc": utc, "kind": kind}


def _edit_rows(run_dir: Path, edit: Callable[[dict[str, Any]], None]) -> None:
    """Apply edit to every per_question.jsonl line (hand-made data)."""
    path = run_dir / "per_question.jsonl"
    rows = read_jsonl(path)
    for row in rows:
        edit(row)
    write_jsonl(path, rows)


@pytest.fixture
def run_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """4-item fake run; the report reads Settings pointing at tmp_path (no overrides)."""
    settings = make_settings(tmp_path)
    monkeypatch.setattr(report, "get_settings", lambda: settings)
    _run(tmp_path, FakePipeline(), settings=settings)
    return tmp_path / "run"


def _with_attempts(run_dir: Path, per_id: dict[str, list[dict[str, Any]]]) -> None:
    def edit(row: dict[str, Any]) -> None:
        row["failed_attempts"] = per_id.get(row["id"], [])

    _edit_rows(run_dir, edit)


@pytest.mark.parametrize(("message", "kind"), MESSAGES)
def test_attempt_kind_from_stored_message(message: str, kind: str) -> None:
    attempt = FailedAttempt.model_validate({k: v for k, v in _attempt(message).items()})
    assert attempt_kind(attempt, ["RateLimitError"]) == kind


def test_stored_kind_wins_over_message() -> None:
    attempt = FailedAttempt.model_validate(_attempt("BadRequestError", kind="structured_output"))
    assert attempt_kind(attempt, ["RateLimitError"]) == "structured_output"


def test_summary_counts_each_kind_from_messages(run_dir: Path) -> None:
    _with_attempts(run_dir, {"q001": [_attempt(m) for m, _ in MESSAGES]})
    o = summarize(run_dir)["overall"]
    assert o["structured_output_failures"] == {"total": 2, "n": 4}
    assert o["items_with_structured_output_failures"]["count"] == 1
    assert o["rate_limited_attempts"] == {"total": 1, "n": 4}
    assert o["transient_call_errors"] == {"total": 1, "n": 4}
    assert o["permanent_call_errors"] == {"total": 1, "n": 4}
    # A bare BadRequestError, a bare WebSearchError and an unknown message.
    assert o["unclassified_call_errors"] == {"total": 3, "n": 4}


def test_summary_rows_keep_existing_labels_and_order(run_dir: Path) -> None:
    md = render_markdown(summarize(run_dir))
    labels = [line.split(" | ")[0].lstrip("| ") for line in md.splitlines() if line.startswith("|")]
    i = labels.index("rate-limited attempts (not counted above)")
    assert labels[i - 2 : i + 1] == [
        "structured_output_failures (failed attempts before success)",
        "items with >= 1 structured_output failure",
        "rate-limited attempts (not counted above)",
    ]
    assert labels[i + 1 : i + 5] == [
        "transient call errors (connection, timeout, 5xx; not counted above)",
        "permanent call errors (auth, plan limit, other 4xx; not counted above)",
        "unclassified call errors (not counted above)",
        "structured-call fallbacks",
    ]


def test_missing_override_file_means_no_overrides(run_dir: Path, tmp_path: Path) -> None:
    assert load_overrides(tmp_path / "results" / "error_reclassifications.json") == []
    _with_attempts(run_dir, {"q002": [_attempt("BadRequestError")]})
    s = summarize(run_dir)
    assert s["overall"]["unclassified_call_errors"]["total"] == 1
    assert "error_reclassifications" not in s
    assert "Note:" not in render_markdown(s)


def _write_overrides(tmp_path: Path, overrides: list[dict[str, Any]]) -> None:
    write_json(tmp_path / "results" / "error_reclassifications.json", {"overrides": overrides})


OVERRIDE = {
    "run": "results/runs/run",
    "item": "q002",
    "kind": "structured_output",
    "utc": UTC,
    "evidence": ["docs/progress/M10-corrective-rag.md, S3 additional facts 3", "run id abc"],
}


def test_override_is_applied_and_footnoted(run_dir: Path, tmp_path: Path) -> None:
    _write_overrides(tmp_path, [OVERRIDE])
    _with_attempts(run_dir, {"q002": [_attempt("BadRequestError")]})
    s = summarize(run_dir)
    assert s["overall"]["structured_output_failures"]["total"] == 1
    assert s["overall"]["unclassified_call_errors"]["total"] == 0
    assert s["per_category"]["multi"]["structured_output_failures"]["total"] == 1  # q002
    assert [o["item"] for o in s["error_reclassifications"]] == ["q002"]
    md = render_markdown(s)
    assert "- Note: run q002: failed-attempt kind set to structured_output" in md
    assert "S3 additional facts 3; run id abc" in md
    compared = render_comparison([run_dir])
    assert "- Note: run q002: failed-attempt kind set to structured_output" in compared


def test_override_for_another_run_or_attempt_is_ignored(run_dir: Path, tmp_path: Path) -> None:
    other_run = {**OVERRIDE, "run": "results/runs/other-run"}
    other_utc = {**OVERRIDE, "utc": "2026-01-01T00:00:00+00:00"}
    _write_overrides(tmp_path, [other_run, other_utc])
    _with_attempts(run_dir, {"q002": [_attempt("BadRequestError")]})
    s = summarize(run_dir)
    assert s["overall"]["unclassified_call_errors"]["total"] == 1
    assert "error_reclassifications" not in s


def test_override_without_utc_applies_to_every_attempt_of_the_item() -> None:
    override = ErrorReclassification.model_validate({**OVERRIDE, "utc": None})
    attempts = [FailedAttempt.model_validate(_attempt("BadRequestError", utc=u)) for u in "ab"]
    kinds, applied = item_kinds("q002", attempts, ["RateLimitError"], [override])
    assert kinds == ["structured_output", "structured_output"] and len(applied) == 2


def test_override_needs_evidence() -> None:
    with pytest.raises(ValueError):
        ErrorReclassification.model_validate({**OVERRIDE, "evidence": []})


def test_runs_before_the_field_show_dash(run_dir: Path) -> None:
    def edit(row: dict[str, Any]) -> None:
        for field in ("structured_output_failures", "rate_limited_attempts"):
            row["scores"].pop(field, None)

    _edit_rows(run_dir, edit)
    o = summarize(run_dir)["overall"]
    assert format_cell(o, "structured_output_failures", "total") == "-"
    assert format_cell(o, "transient_call_errors", "total") == "-"


# Structured-call fallbacks (diagnostics["fallbacks"], M11).


def test_no_diagnostics_key_means_no_fallbacks(run_dir: Path) -> None:
    rows = read_jsonl(run_dir / "per_question.jsonl")
    assert all("diagnostics" not in row["result"] for row in rows)
    o = summarize(run_dir)["overall"]
    assert o["structured_call_fallbacks"]["count"] == 0
    assert format_cell(o, "structured_call_fallbacks", "fallbacks") == "0.000 (0/4)"


def test_fallbacks_rate_and_count_per_type(run_dir: Path) -> None:
    per_id = {
        "q001": ["verify_failed", "verify_failed"],
        "q002": ["decide_failed"],
        "q004": [],
    }

    def edit(row: dict[str, Any]) -> None:
        if row["id"] in per_id:
            row["result"]["diagnostics"] = {"fallbacks": per_id[row["id"]], "other": 1}

    _edit_rows(run_dir, edit)
    s = summarize(run_dir)
    o = s["overall"]
    assert o["structured_call_fallbacks"]["count"] == 2 and o["structured_call_fallbacks"]["n"] == 4
    assert format_cell(o, "structured_call_fallbacks", "fallbacks") == (
        "0.500 (2/4); decide_failed 1, verify_failed 2, regenerate_failed 0"
    )
    assert "| structured-call fallbacks | 0.500 (2/4); decide_failed 1" in render_markdown(s)


def test_pipeline_result_diagnostics_dump_rules() -> None:
    base = {
        "question": "q",
        "pipeline": "self_rag",
        "answer": {"text": "a", "citations": [], "abstained": False},
        "contexts": [],
        "trace": [],
        "llm_calls": 1,
        "latency_ms": 5,
    }
    empty = PipelineResult.model_validate(base)
    assert empty.diagnostics == {}
    assert "diagnostics" not in empty.model_dump()
    assert '"diagnostics"' not in empty.model_dump_json()
    full = PipelineResult.model_validate({**base, "diagnostics": {"fallbacks": ["verify_failed"]}})
    again = PipelineResult.model_validate_json(full.model_dump_json())
    assert again.diagnostics == {"fallbacks": ["verify_failed"]}
    assert again.model_dump()["diagnostics"] == {"fallbacks": ["verify_failed"]}
