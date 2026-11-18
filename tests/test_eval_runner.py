"""Tests for deterministic scoring, the eval runner and the judge pass (no network)."""

from pathlib import Path

import pytest
from eval_fakes import (
    GEN_MODEL,
    FakeClock,
    FakeJudgeLLM,
    FakePipeline,
    make_chunk,
    make_items,
    make_settings,
)

from ragdocs.eval.judge import build_judge_messages, judge_cache_key, load_records
from ragdocs.eval.judge_run import run_judge
from ragdocs.eval.report import render_markdown, summarize
from ragdocs.eval.runner import EXIT_OK, EXIT_PAUSED, EvalSetMismatch, run_eval
from ragdocs.eval.scoring import must_mention_coverage, score_item
from ragdocs.eval.throttle import BudgetStore, RollingBudget
from ragdocs.io_utils import read_json, read_jsonl
from ragdocs.schemas import Answer, JudgeVerdict, PipelineResult, TokenUsageRecord


def _result(text: str, abstained: bool, contexts: list) -> PipelineResult:
    return PipelineResult(
        question="q",
        pipeline="p",
        answer=Answer(text=text, citations=[], abstained=abstained),
        contexts=contexts,
        trace=[],
        llm_calls=2,
        latency_ms=50,
        used_web=False,
    )


def test_must_mention_case_insensitive_substring() -> None:
    assert must_mention_coverage("use StateGraph here", ["stategraph", "ADD_NODE"]) == 0.5
    assert must_mention_coverage("x", []) is None


def test_score_item_answerable() -> None:
    """Hit and recall are on the contexts; recall counts matched evidence entries."""
    item = make_items()[1]  # multi: evidence doc.mdx#a2 and other.mdx#z
    contexts = [make_chunk(1), make_chunk(2)]
    usage = TokenUsageRecord(tokens_in=10, tokens_out=5)
    s = score_item(item, _result("Use send.", False, contexts), usage, k=5)
    assert s.false_abstention is False
    assert s.context_hit_at_5 == 1.0
    assert s.context_evidence_recall_at_5 == 0.5
    assert s.must_mention_coverage == 1.0
    assert s.abstention_correct is None and s.hallucinated is None
    assert (s.llm_calls, s.latency_ms, s.tokens_in, s.tokens_out) == (2, 50, 10, 5)


def test_score_item_hit_respects_k() -> None:
    item = make_items()[0]
    s = score_item(
        item, _result("x", False, [make_chunk(1), make_chunk(2)]), TokenUsageRecord(), k=1
    )
    assert s.context_hit_at_5 == 0.0


def test_score_item_unanswerable() -> None:
    item = make_items()[3]
    s = score_item(item, _result("made up", False, []), TokenUsageRecord(), k=5)
    assert s.abstention_correct is False and s.hallucinated is True
    assert s.false_abstention is None and s.context_hit_at_5 is None
    s2 = score_item(item, _result("abstain", True, []), TokenUsageRecord(), k=5)
    assert s2.abstention_correct is True and s2.hallucinated is False


def _budgets(tmp_path: Path, clock: FakeClock, rpd: int = 100) -> dict[str, RollingBudget]:
    store = BudgetStore(tmp_path / "cache" / "budget.json")
    return {
        GEN_MODEL: RollingBudget(
            GEN_MODEL, 8000, 30, rpd, 200000, store=store, clock=clock, sleep=clock.sleep
        )
    }


def _run(tmp_path: Path, pipeline: FakePipeline, settings=None, rpd: int = 100) -> int:
    settings = settings or make_settings(tmp_path)
    return run_eval(
        "fake",
        tmp_path / "run",
        settings=settings,
        pipeline=pipeline,
        budgets=_budgets(tmp_path, FakeClock(), rpd),
        git_check=lambda s: True,
        out=lambda m: None,
    )


def test_run_eval_writes_records_in_id_order_with_context_texts(tmp_path: Path) -> None:
    pipeline = FakePipeline()
    assert _run(tmp_path, pipeline) == EXIT_OK
    rows = read_jsonl(tmp_path / "run" / "per_question.jsonl")
    assert [r["id"] for r in rows] == ["q001", "q002", "q003", "q004"]
    assert rows[0]["context_texts"] == [f"Text of chunk {i}." for i in (1, 2, 3)]
    assert rows[0]["scores"]["context_hit@5"] == 1.0
    assert rows[0]["usage"]["by_model"][GEN_MODEL]["input_tokens"] == 1000
    assert rows[0]["langsmith_run_id"] is None
    assert all(r["verdict"] is None for r in rows)
    assert [r["judge_eligible"] for r in rows] == [True, True, False, False]
    config = read_json(tmp_path / "run" / "config.json")
    assert config["tracing_enabled"] is False
    assert "groq_api_key" not in config["settings"]
    assert (tmp_path / "run" / "summary.md").is_file()


def test_run_eval_resume_skips_done_ids(tmp_path: Path) -> None:
    first = FakePipeline()
    first.fail_on = {"Q3?"}
    assert _run(tmp_path, first) == EXIT_PAUSED
    assert first.questions == ["Q1?", "Q2?", "Q3?", "Q3?"]  # two attempts on q003
    second = FakePipeline()
    assert _run(tmp_path, second) == EXIT_OK
    assert second.questions == ["Q3?", "Q4?"]
    rows = read_jsonl(tmp_path / "run" / "per_question.jsonl")
    assert len(rows) == 4
    # Failures from the paused invocation are counted on the item that later succeeded.
    by_id = {r["id"]: r for r in rows}
    assert by_id["q003"]["scores"]["structured_output_failures"] == 2
    assert [a["stage"] for a in by_id["q003"]["failed_attempts"]] == ["generate", "generate"]
    assert by_id["q001"]["scores"]["structured_output_failures"] == 0
    summary = summarize(tmp_path / "run")["overall"]
    assert summary["structured_output_failures"] == {"total": 2, "n": 4}
    assert summary["items_with_structured_output_failures"]["count"] == 1
    assert "| structured_output_failures (failed attempts before success) | 2 (n=4) |" in (
        render_markdown(summarize(tmp_path / "run"))
    )


def test_run_eval_pauses_on_daily_limit(tmp_path: Path) -> None:
    """With 3 requests per day (x 0.9 safety = 2.7), two items run, then exit code 3."""
    pipeline = FakePipeline()
    assert _run(tmp_path, pipeline, rpd=3) == EXIT_PAUSED
    assert len(read_jsonl(tmp_path / "run" / "per_question.jsonl")) == 2


def test_run_eval_refuses_changed_eval_set(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, eval_set_sha256="0" * 64)
    with pytest.raises(EvalSetMismatch):
        _run(tmp_path, FakePipeline(), settings=settings)
    assert not (tmp_path / "run").exists()


def test_run_eval_refuses_when_git_diff_fails(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    with pytest.raises(EvalSetMismatch):
        run_eval(
            "fake",
            tmp_path / "run",
            settings=settings,
            pipeline=FakePipeline(),
            budgets={},
            git_check=lambda s: False,
            out=lambda m: None,
        )


class _DictCache(dict):
    """dict with diskcache's get/set used by judge_item."""

    def set(self, key: str, value: object) -> None:
        self[key] = value


def _judge(tmp_path: Path, llm: FakeJudgeLLM, settings=None) -> int:
    settings = settings or make_settings(tmp_path)
    clock = FakeClock()
    budget = RollingBudget("gemini-3.5-flash-lite", 250000, 15, 500, clock=clock, sleep=clock.sleep)
    return run_judge(
        tmp_path / "run",
        settings=settings,
        llm=llm,
        budget=budget,
        cache=_DictCache(),
        out=lambda m: None,
    )


def test_judge_skips_abstained_and_unanswerable(tmp_path: Path) -> None:
    _run(tmp_path, FakePipeline())
    llm = FakeJudgeLLM()
    assert _judge(tmp_path, llm) == EXIT_OK
    rows = read_jsonl(tmp_path / "run" / "judge_v1.jsonl")
    assert [r["id"] for r in rows] == ["q001", "q002"]
    assert len(llm.calls) == 2
    # per_question.jsonl is untouched
    assert all(r["verdict"] is None for r in read_jsonl(tmp_path / "run" / "per_question.jsonl"))


def test_judge_resume_and_retry(tmp_path: Path) -> None:
    """A failure on both attempts pauses; the re-run judges only what is left."""
    _run(tmp_path, FakePipeline())
    assert _judge(tmp_path, FakeJudgeLLM(fail_times=2)) == EXIT_PAUSED
    llm = FakeJudgeLLM()
    assert _judge(tmp_path, llm) == EXIT_OK
    assert len(llm.calls) == 2
    assert len(read_jsonl(tmp_path / "run" / "judge_v1.jsonl")) == 2


def test_judge_cache_avoids_second_call(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    _run(tmp_path, FakePipeline(), settings=settings)
    record = load_records(tmp_path / "run")[0]
    from ragdocs.eval.judge import judge_item

    cache = _DictCache()
    llm = FakeJudgeLLM()
    judge_item(record, llm=llm, cache=cache, settings=settings)
    judge_item(record, llm=llm, cache=cache, settings=settings)
    assert len(llm.calls) == 1
    bumped = make_settings(tmp_path, judge_prompt_version=settings.judge_prompt_version + 1)
    assert judge_cache_key(record, settings) != judge_cache_key(record, bumped)


def test_judge_messages_number_and_flag_excerpts(tmp_path: Path) -> None:
    _run(tmp_path, FakePipeline())
    record = load_records(tmp_path / "run")[0]  # cites excerpt 2 only
    user = build_judge_messages(record)[1].content
    assert "[1] NOT CITED Title 1 > H1" in user
    assert "[2] CITED Title 2 > H2" in user
    assert "[3] NOT CITED Title 3 > H3" in user
    assert "StateGraph, add_node" in user and "R1" in user


def test_verdict_rationale_truncated_to_60_words() -> None:
    v = JudgeVerdict(correctness=1, citation_support=0, rationale="w " * 80)
    assert len(v.rationale.split()) == 60


def test_rate_limit_failures_counted_separately(tmp_path: Path) -> None:
    """A 429 is waited out (default 60 s, 3 waits per item), then the run pauses.

    The attempts are logged but not counted as structured-output failures.
    """
    first = FakePipeline()
    first.fail_on = {"Q1?"}
    first.fail_message = "RateLimitError: Error code: 429"
    assert _run(tmp_path, first) == EXIT_PAUSED
    assert first.questions == ["Q1?"] * 4  # 1 + 3 waits
    assert _run(tmp_path, FakePipeline()) == EXIT_OK
    row = read_jsonl(tmp_path / "run" / "per_question.jsonl")[0]
    assert row["scores"]["structured_output_failures"] == 0
    assert row["scores"]["rate_limited_attempts"] == 4
    assert len(row["failed_attempts"]) == 4


TPD_429 = (
    "RateLimitError: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` "
    "on tokens per day (TPD): Limit 200000, Used 197584, Requested 2562. "
    "Please try again in 1m3.504s."
)


class _FailOnce(FakePipeline):
    """Fails the first n calls with fail_message, then answers."""

    def __init__(self, n: int) -> None:
        super().__init__()
        self.n = n

    def stream(self, question, run_metadata=None, callbacks=None):  # type: ignore[no-untyped-def]
        if self.n > 0:
            self.n -= 1
            self.fail_on = {question}
        else:
            self.fail_on = set()
        yield from super().stream(question, run_metadata, callbacks)


def test_daily_429_waits_retry_after_and_logs_model_miss(tmp_path: Path) -> None:
    """One TPD 429: sleep 63.5 s + 1 s, log one model miss, then the item succeeds."""
    pipeline = _FailOnce(1)
    pipeline.fail_message = TPD_429
    clock = FakeClock()
    settings = make_settings(tmp_path)
    code = run_eval(
        "fake",
        tmp_path / "run",
        settings=settings,
        pipeline=pipeline,
        budgets={GEN_MODEL: _budgets(tmp_path, clock)[GEN_MODEL]},
        git_check=lambda s: True,
        out=lambda m: None,
    )
    assert code == EXIT_OK
    assert any(abs(s - 64.504) < 0.01 for s in clock.sleeps)
    misses = read_jsonl(tmp_path / "cache" / "budget_model_misses.jsonl")
    assert len(misses) == 1 and misses[0]["model"] == GEN_MODEL


def test_second_model_miss_pauses_run(tmp_path: Path) -> None:
    pipeline = _FailOnce(2)
    pipeline.fail_message = TPD_429
    assert _run(tmp_path, pipeline) == EXIT_PAUSED
    assert len(read_jsonl(tmp_path / "cache" / "budget_model_misses.jsonl")) == 2
