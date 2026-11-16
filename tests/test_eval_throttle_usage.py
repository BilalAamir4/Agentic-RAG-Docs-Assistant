"""Tests for TokenUsage and RollingBudget (fake clock, no network)."""

from uuid import uuid4

import pytest
from eval_fakes import FakeClock, emit_usage
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from ragdocs.eval.throttle import BudgetStore, DailyLimitReached, RollingBudget, UsageEstimator
from ragdocs.providers.usage import TokenUsage


def test_token_usage_per_model_and_totals() -> None:
    """Usage is summed per ls_model_name and over all models."""
    u = TokenUsage()
    emit_usage([u], "m1", 100, 10)
    emit_usage([u], "m1", 50, 5)
    emit_usage([u], "m2", 7, 3)
    rec = u.record()
    assert rec.tokens_in == 157 and rec.tokens_out == 18 and rec.usage_missing == 0
    assert rec.by_model["m1"].calls == 2 and rec.by_model["m1"].input_tokens == 150
    assert rec.by_model["m2"].output_tokens == 3


def test_token_usage_llm_output_fallback_and_missing() -> None:
    """Groq-style llm_output is used when usage_metadata is absent; else counted missing."""
    u = TokenUsage()
    run_a, run_b = uuid4(), uuid4()
    msg = AIMessage(content="")
    out = {"token_usage": {"prompt_tokens": 11, "completion_tokens": 4}, "model_name": "g"}
    u.on_llm_end(
        LLMResult(generations=[[ChatGeneration(message=msg)]], llm_output=out), run_id=run_a
    )
    u.on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]), run_id=run_b)
    rec = u.record()
    assert rec.by_model["g"].input_tokens == 11 and rec.by_model["g"].output_tokens == 4
    assert rec.by_model["unknown"].usage_missing == 1
    assert rec.usage_missing == 1


def _budget(clock: FakeClock, **kw: object) -> RollingBudget:
    args = {"tokens_per_min": 1000, "requests_per_min": 10, "requests_per_day": 100}
    args.update(kw)
    return RollingBudget("m", safety=0.9, clock=clock, sleep=clock.sleep, **args)  # type: ignore[arg-type]


def test_wait_for_returns_immediately_when_window_fits() -> None:
    clock = FakeClock()
    b = _budget(clock)
    assert b.wait_for(800, 1) == 0.0
    assert clock.sleeps == []


def test_wait_for_sleeps_until_oldest_event_leaves_window() -> None:
    """800 recorded tokens + 200 estimate > 900 cap, so it waits about 60 s."""
    clock = FakeClock()
    b = _budget(clock)
    b.record(800, 1)
    clock.t += 10
    slept = b.wait_for(200, 1)
    assert 50.0 <= slept <= 50.1
    assert b.wait_for(200, 1) == 0.0


def test_wait_for_respects_request_cap() -> None:
    """requests_per_min 10 x 0.9 = 9 requests fit; the 10th waits."""
    clock = FakeClock()
    b = _budget(clock)
    for _ in range(9):
        b.wait_for(1, 1)
        b.record(1, 1)
    assert b.wait_for(1, 1) > 0


def test_daily_request_limit_raises() -> None:
    clock = FakeClock()
    b = _budget(clock, requests_per_day=3)
    b.record(1, 3)
    with pytest.raises(DailyLimitReached) as exc:
        b.wait_for(1, 1)
    assert exc.value.kind == "requests"
    assert exc.value.resets_at.timestamp() > clock()


def test_daily_token_limit_raises() -> None:
    clock = FakeClock()
    b = _budget(clock, tokens_per_day=5000)
    b.record(4500, 1)
    with pytest.raises(DailyLimitReached) as exc:
        b.wait_for(600, 1)
    assert exc.value.kind == "tokens"


def test_daily_token_limit_applies_safety() -> None:
    """4000 + 600 = 4600 is under 5000 but over 0.9 x 5000 = 4500, so it pauses."""
    clock = FakeClock()
    b = _budget(clock, tokens_per_day=5000)
    b.record(4000, 1)
    with pytest.raises(DailyLimitReached):
        b.wait_for(600, 1)
    assert _budget(FakeClock(), tokens_per_day=5000).wait_for(4500, 1) == 0.0


def test_daily_counts_shared_through_store_and_reset_next_day(tmp_path) -> None:
    """A second budget on the same file sees the first one's counts; a new day resets."""
    clock = FakeClock()
    store = BudgetStore(tmp_path / "budget.json")
    _budget(clock, store=store).record(10, 2)
    second = _budget(clock, store=store)
    assert second.daily_used() == (2, 10)
    clock.t += 86400
    assert second.daily_used() == (0, 0)


def test_quota_day_uses_budget_timezone() -> None:
    """2026-11-16 03:00 UTC is still 2026-11-15 in America/Los_Angeles."""
    clock = FakeClock(start=1_794_798_000.0)  # 2026-11-16T03:00:00Z
    assert _budget(clock, timezone="UTC").day() == "2026-11-16"
    assert _budget(clock, timezone="America/Los_Angeles").day() == "2026-11-15"


def test_usage_estimator_max_observed() -> None:
    est = UsageEstimator(3000)
    assert est.estimate("m") == (3000, 1)
    est.observe({"m": (1200, 1)})
    est.observe({"m": (900, 2)})
    assert est.estimate("m") == (1200, 2)
    assert est.estimate("unused") == (0, 0)


def test_token_usage_counts_failed_calls() -> None:
    """A call that ends in on_llm_error is counted as a call without usage data."""
    u = TokenUsage()
    run_id = uuid4()
    u.on_chat_model_start({}, [[]], run_id=run_id, metadata={"ls_model_name": "m1"})
    u.on_llm_error(RuntimeError("400 tool_use_failed"), run_id=run_id)
    rec = u.record()
    assert rec.by_model["m1"].calls == 1 and rec.by_model["m1"].usage_missing == 1
    assert rec.tokens_in == 0 and rec.usage_missing == 1
