"""Tests for the RAGAS handoff export, the tool command and the budget file contract (M09).

No network. tools/ragas_budget.py and the pure helpers of tools/ragas_score.py are
standard library at import time, so they load in the main venv.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest
from eval_fakes import FakeClock, FakePipeline, make_settings
from test_eval_runner import _run

from ragdocs.eval.judge import load_records
from ragdocs.eval.ragas_export import (
    INPUT_FIELDS,
    RAGAS_INPUT_FILE,
    build_ragas_input,
    export_ragas_input,
    ragas_tool_args,
    ragas_tool_env,
)
from ragdocs.eval.throttle import BudgetStore, RollingBudget
from ragdocs.io_utils import read_jsonl, read_text, write_text

TOOLS = Path(__file__).resolve().parent.parent / "tools"
START = 1_794_819_600.0  # 2026-11-16T09:00:00Z


def _load_tool(name: str) -> ModuleType:
    """Import tools/<name>.py by path, restoring os.environ (the scorer sets flags)."""
    saved = dict(os.environ)
    sys.path.insert(0, str(TOOLS))
    try:
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(TOOLS))
        os.environ.clear()
        os.environ.update(saved)


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    _run(tmp_path, FakePipeline())
    return tmp_path / "run"


def test_projection_fields_and_context_order(run_dir: Path) -> None:
    records = load_records(run_dir)
    rows = build_ragas_input(records)
    assert [r["id"] for r in rows] == ["q001", "q002", "q003", "q004"]
    for row, rec in zip(rows, records, strict=True):
        assert tuple(row) == INPUT_FIELDS
        assert row["user_input"] == rec.question
        assert row["response"] == rec.result.answer.text
        assert row["retrieved_contexts"] == rec.context_texts  # stored order
        assert row["reference"] == rec.reference_answer


def test_eligibility_flags_follow_d19(run_dir: Path) -> None:
    flags = {r["id"]: r["eligible"] for r in build_ragas_input(load_records(run_dir))}
    assert all(flags["q001"].values()) and all(flags["q002"].values())
    assert flags["q003"] == {  # abstained answer, contexts present
        "faithfulness": False,
        "response_relevancy": False,
        "context_precision": True,
        "context_recall": True,
    }
    assert not any(flags["q004"].values())  # unanswerable: never scored


def test_no_contexts_means_no_context_metrics(run_dir: Path) -> None:
    record = load_records(run_dir)[0]
    empty = record.model_copy(update={"context_texts": []})
    assert build_ragas_input([empty])[0]["eligible"]["context_recall"] is False


def test_export_is_idempotent_and_never_overwrites(run_dir: Path) -> None:
    path, rows = export_ragas_input(run_dir)
    assert path.name == RAGAS_INPUT_FILE and read_jsonl(path) == rows
    export_ragas_input(run_dir)  # identical file: kept
    write_text(path, read_text(path).replace("q001", "q999"))
    with pytest.raises(FileExistsError):
        export_ragas_input(run_dir)


def test_tool_args_and_env_come_from_settings(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, google_api_key="test-key-not-real")
    args = ragas_tool_args(settings, tmp_path / "in.jsonl", tmp_path / "out", "abc")
    pairs = dict(zip(args[::2], args[1::2], strict=True))
    assert pairs["--llm-model"] == "gemini-3.1-flash-lite"
    assert pairs["--embedding-model"] == settings.embedding_model
    assert pairs["--llm-limits"] == "15,250000,500"
    assert "test-key-not-real" not in args
    env = ragas_tool_env(
        settings, {"LANGSMITH_API_KEY": "x", "LANGCHAIN_TRACING_V2": "1", "A": "b"}
    )
    assert env["GOOGLE_API_KEY"] == "test-key-not-real" and env["A"] == "b"
    assert not any(k.startswith(("LANGSMITH", "LANGCHAIN")) for k in env)


def test_budget_file_written_by_tool_matches_ragdocs_contract(tmp_path: Path) -> None:
    """Both writers produce byte-identical files and each reads the other's events."""
    rb = _load_tool("ragas_budget")
    clock = FakeClock(start=START)
    tool_store = rb.BudgetFile(tmp_path / "tool.json", clock=clock)
    ours = BudgetStore(tmp_path / "ours.json", clock=clock)
    for model, req, tok in (("gemini-3.1-flash-lite", 1, 2400), ("gemini-embedding-001", 1, 12)):
        tool_store.add(model, req, tok)
        ours.add(model, req, tok)
        clock.t += 1.5
    assert read_text(tmp_path / "tool.json") == read_text(tmp_path / "ours.json")
    assert BudgetStore(tmp_path / "tool.json").events("gemini-3.1-flash-lite", 0) == [
        (START, 1, 2400)
    ]
    assert rb.BudgetFile(tmp_path / "ours.json").used_since("gemini-embedding-001", 0) == (1, 12)


def test_tool_daily_cap_matches_rolling_budget(tmp_path: Path) -> None:
    """Calendar day, Pacific, cap = 500 x 0.9: 449 used fits 1 more request, not 2."""
    rb = _load_tool("ragas_budget")
    clock = FakeClock(start=START)
    store = rb.BudgetFile(tmp_path / "b.json", clock=clock)
    store.add("m", 449, 0)
    tool = rb.CalendarBudget(
        "m", store, requests_per_min=15, tokens_per_min=250000, requests_per_day=500,
        safety=0.9, timezone="America/Los_Angeles", sleep=clock.sleep,
    )  # fmt: skip
    ours = RollingBudget(
        "m", 250000, 15, 500, store=BudgetStore(tmp_path / "b.json", clock=clock),
        timezone="America/Los_Angeles", clock=clock, sleep=clock.sleep,
    )  # fmt: skip
    assert tool.daily_used() == ours.daily_used() == (449, 0)
    tool.check_daily(1)
    with pytest.raises(rb.DailyLimitReached) as exc:
        tool.check_daily(2)
    assert exc.value.resets_at == ours.resets_at()


def test_tool_summary_cache_key_and_plan(tmp_path: Path, capsys) -> None:
    rs = _load_tool("ragas_score")
    rows = [
        {"id": "a", "category": "single", "user_input": "q", "response": "r",
         "retrieved_contexts": ["c1", "c2"], "reference": "ref",
         "eligible": dict.fromkeys(rs.METRICS, True)},
        {"id": "b", "category": "multi", "user_input": "q2", "response": "r2",
         "retrieved_contexts": ["c"], "reference": "ref2",
         "eligible": {"faithfulness": False, "response_relevancy": False,
                      "context_precision": True, "context_recall": True}},
    ]  # fmt: skip
    scores = [
        {"id": "a", "category": "single", "faithfulness": 0.5, "response_relevancy": None,
         "context_precision": 1.0, "context_recall": 1.0,
         "errors": {"response_relevancy": "ValueError: x"}},
        {"id": "b", "category": "multi", "context_precision": 0.0, "context_recall": None,
         "errors": {"context_recall": "NaN"}},
    ]  # fmt: skip
    s = rs.summarize(rows, scores)["metrics"]
    assert s["faithfulness"] == {"mean": 0.5, "n_eligible": 1, "n_scored": 1, "n_errored": 0}
    assert s["response_relevancy"]["mean"] is None and s["response_relevancy"]["n_errored"] == 1
    assert s["context_precision"]["mean"] == 0.5 and s["context_recall"]["n_scored"] == 1
    key = rs.cache_key("0.4.4", "faithfulness", "llm", "emb", rows[0])
    assert key == rs.cache_key("0.4.4", "faithfulness", "llm", "emb", dict(rows[0]))
    assert key != rs.cache_key("0.4.4", "context_recall", "llm", "emb", rows[0])
    assert key != rs.cache_key("0.4.5", "faithfulness", "llm", "emb", rows[0])
    args = rs.parse_args(
        ["--input", "i", "--out-dir", "o", "--budget-file", str(tmp_path / "b.json"),
         "--cache-dir", "c", "--llm-model", "llm", "--embedding-model", "emb",
         "--llm-limits", "15,250000,10", "--embedding-limits", "100,30000,1000",
         "--timezone", "America/Los_Angeles", "--safety", "1.0", "--window-s", "60",
         "--strictness", "3", "--max-attempts", "3", "--timeout-s", "180",
         "--llm-calls", '{"faithfulness": 2, "response_relevancy": 3, '
         '"context_precision": 5, "context_recall": 1}',
         "--embedding-requests", '{"response_relevancy": 2}', "--tokens-per-call", "2500",
         "--rpm-ceiling", "12",
         "--error-log", "e.jsonl", "--partial-dir", "p"]
    )  # fmt: skip
    # LLM: 1 x 2 + 1 x 3 + 2 x 5 + 2 x 1 = 17 requests over a cap of 10 per day: 2 days.
    assert rs.budget_plan(rows, args, rs.make_budgets(args)) == 2
    assert "total 17 requests" in capsys.readouterr().out
    # Cache check: keys ignore --out-dir and the cache path; only D19 key fields count.
    other = rs.parse_args([*_argv_with(args, "--out-dir", "elsewhere")])
    cache = {rs.cache_key("0.4.4", m, "llm", "emb", rows[0]): {"value": 1.0} for m in rs.METRICS}
    cache[rs.cache_key("0.4.4", "context_precision", "llm", "emb", rows[1])] = {"value": None}
    report = rs.cache_report(rows, other, cache, "0.4.4")
    assert report["items_fully_cached"] == 1
    assert report["metrics"]["context_precision"] == {"eligible": 2, "cached": 2, "missing": []}
    assert report["metrics"]["context_recall"] == {"eligible": 2, "cached": 1, "missing": ["b"]}
    assert (report["llm_requests_needed"], report["embedding_requests_needed"]) == (1, 0)
    changed = [dict(rows[0], response="r changed"), rows[1]]
    assert rs.cache_report(changed, other, cache, "0.4.4")["items_fully_cached"] == 0


def _argv_with(args, flag: str, value: str) -> list[str]:
    """Rebuild a minimal argv from parsed args with one flag replaced (out-dir check)."""
    argv = ["--input", "i", "--out-dir", "o", "--budget-file", "b", "--cache-dir", "c",
            "--llm-model", args.llm_model, "--embedding-model", args.embedding_model,
            "--llm-limits", "15,250000,10", "--embedding-limits", "100,30000,1000",
            "--timezone", "UTC", "--safety", "1.0", "--window-s", "60",
            "--strictness", "3", "--max-attempts", "3", "--timeout-s", "180",
            "--llm-calls", json.dumps(args.llm_calls),
            "--embedding-requests", json.dumps(args.embedding_requests),
            "--tokens-per-call", "2500", "--cache-check", "--rpm-ceiling", "12",
            "--error-log", "e.jsonl", "--partial-dir", "p"]  # fmt: skip
    argv[argv.index(flag) + 1] = value
    return argv


def test_tool_throttle_applies_rpm_ceiling_per_call(tmp_path: Path) -> None:
    """15 RPM x 0.9 = 13.5, lowered to 12: the 13th call in a minute waits."""
    rb = _load_tool("ragas_budget")
    clock = FakeClock(start=START)
    store = rb.BudgetFile(tmp_path / "b.json", clock=clock)
    budget = rb.CalendarBudget(
        "m", store, requests_per_min=15, tokens_per_min=250000, requests_per_day=500,
        safety=0.9, timezone="UTC", sleep=clock.sleep, rpm_ceiling=12,
    )  # fmt: skip
    assert budget.minute_cap == 12
    for _ in range(12):
        assert budget.throttle(100) == 0
        budget.record(1, 100)
    assert budget.throttle(100) > 0  # waited for the window to roll
    no_ceiling = rb.CalendarBudget(
        "m", store, requests_per_min=15, tokens_per_min=250000, requests_per_day=500,
        safety=0.9, timezone="UTC", sleep=clock.sleep,
    )  # fmt: skip
    assert no_ceiling.minute_cap == pytest.approx(13.5)


def test_tool_error_log_keeps_full_chain_and_provider_details(tmp_path: Path) -> None:
    rs = _load_tool("ragas_score")

    class FakeAPIError(Exception):
        code, status = 429, "RESOURCE_EXHAUSTED"
        details = {"error": {"details": [{"violations": [{"quotaId": "PerDay"}]}]}}

    long_text = "429 RESOURCE_EXHAUSTED " + "x" * 1000
    try:
        try:
            raise FakeAPIError(long_text)
        except FakeAPIError as inner:
            raise RuntimeError("wrapped") from inner
    except RuntimeError as exc:
        rs.log_error(tmp_path / "e.jsonl", "llm_attempt", exc, id="q009", metric="faithfulness")
    rec = json.loads((tmp_path / "e.jsonl").read_text(encoding="utf-8"))
    assert rec["id"] == "q009" and rec["kind"] == "llm_attempt" and rec["quota"] is True
    assert [c["type"] for c in rec["chain"]] == ["RuntimeError", "FakeAPIError"]
    assert rec["chain"][1]["message"] == long_text  # not truncated
    assert rec["chain"][1]["details"]["error"]["details"][0]["violations"][0]["quotaId"] == "PerDay"
