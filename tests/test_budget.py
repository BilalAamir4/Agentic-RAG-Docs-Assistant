"""Tests for the rolling 24-hour budget, the v2 store and the budget recorder (no network)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from eval_fakes import FakeClock, emit_usage
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from ragdocs.eval.budget_recorder import (
    install_budget_recorder,
    recorder_active,
    uninstall_budget_recorder,
)
from ragdocs.eval.throttle import (
    DAY_S,
    WINDOW_BUCKET,
    WINDOW_ROLLING,
    BudgetStore,
    DailyLimitReached,
    RollingBudget,
    parse_retry_after,
)
from ragdocs.io_utils import read_json, write_json
from ragdocs.providers.usage import notify_usage

START = 1_794_819_600.0  # 2026-11-16T09:00:00Z


def _rolling(clock: FakeClock, store: BudgetStore, tpd: int = 200_000) -> RollingBudget:
    return RollingBudget(
        "g",
        tokens_per_min=10**9,
        requests_per_min=10**6,
        requests_per_day=1000,
        tokens_per_day=tpd,
        store=store,
        daily_window=WINDOW_ROLLING,
        clock=clock,
        sleep=clock.sleep,
    )


def test_rolling_window_sums_trailing_24h_only(tmp_path: Path) -> None:
    clock = FakeClock(start=START)
    store = BudgetStore(tmp_path / "b.json", clock=clock)
    b = _rolling(clock, store)
    b.record(100_000, 50)
    clock.t += 3600
    b.record(60_000, 20)
    assert b.daily_used() == (70, 160_000)
    clock.t = START + DAY_S + 1  # first event has left the window, not at UTC midnight
    assert b.daily_used() == (20, 60_000)


def test_rolling_resets_at_is_when_enough_events_expire(tmp_path: Path) -> None:
    """Cap 180K; 170K used in two events; a 30K estimate fits once the first expires."""
    clock = FakeClock(start=START)
    store = BudgetStore(tmp_path / "b.json", clock=clock)
    b = _rolling(clock, store)
    b.record(110_000, 50)
    clock.t += 1800
    b.record(60_000, 20)
    with pytest.raises(DailyLimitReached) as exc:
        b.wait_for(30_000, 1)
    assert exc.value.resets_at.timestamp() == pytest.approx(START + DAY_S, abs=0.01)


def test_store_v2_format_and_retention(tmp_path: Path) -> None:
    clock = FakeClock(start=START)
    path = tmp_path / "b.json"
    store = BudgetStore(path, clock=clock)
    store.add("m", 1, 10)
    clock.t += 3 * DAY_S
    store.add("m", 2, 20)  # prunes the event older than 2 days
    data = read_json(path)
    assert data["version"] == 2
    assert [e[1:] for e in data["events"]["m"]] == [[2, 20]]


def test_legacy_format_migrates_to_end_of_day_event(tmp_path: Path) -> None:
    """v1 totals become one event at the end of their UTC date, capped at now."""
    path = tmp_path / "b.json"
    write_json(path, {"m": {"date": "2026-11-15", "requests": 5, "tokens": 500}})
    clock = FakeClock(start=START)  # 2026-11-16T09:00Z, after the end of 2026-11-15
    store = BudgetStore(path, clock=clock)
    assert store.events("m", 0) == [(START - 9 * 3600, 5, 500)]
    write_json(path, {"m": {"date": "2026-11-16", "requests": 5, "tokens": 500}})
    assert store.events("m", 0) == [(START, 5, 500)]


@pytest.fixture
def recorder_store(tmp_path: Path) -> Iterator[BudgetStore]:
    store = BudgetStore(tmp_path / "b.json")
    install_budget_recorder(store=store)
    yield store
    uninstall_budget_recorder()
    assert not recorder_active()


def test_recorder_persists_each_call_and_failed_calls(recorder_store: BudgetStore) -> None:
    recorder = install_budget_recorder(store=recorder_store)
    emit_usage([recorder], "openai/gpt-oss-120b", 1000, 200)
    recorder.on_chat_model_start({}, [[]], run_id=_uuid(), metadata={"ls_model_name": "x"})
    recorder.on_llm_error(RuntimeError("400"), run_id=_last_run(recorder))
    assert recorder_store.used_since("openai/gpt-oss-120b", 0) == (1, 1200)
    assert recorder_store.used_since("x", 0) == (1, 0)


def test_recorder_sees_chat_models_without_explicit_callbacks(
    recorder_store: BudgetStore,
) -> None:
    """The configure hook adds the recorder to every LangChain run in the process."""
    FakeListChatModel(responses=["hi"]).invoke("hello")
    assert sum(recorder_store.used_since(m, 0)[0] for m in recorder_store.models()) == 1


def test_recorder_records_embedding_listener_calls(recorder_store: BudgetStore) -> None:
    notify_usage("gemini-embedding-001", 1, 12)
    assert recorder_store.used_since("gemini-embedding-001", 0) == (1, 12)


def test_no_recording_without_recorder(tmp_path: Path) -> None:
    uninstall_budget_recorder()
    notify_usage("gemini-embedding-001", 1, 12)  # no listener: nothing happens
    assert not (tmp_path / "b.json").exists()


def _uuid() -> Any:
    from uuid import uuid4

    return uuid4()


def _last_run(recorder: Any) -> Any:
    return next(iter(recorder._run_models))


def _bucket(clock: FakeClock, store: BudgetStore) -> RollingBudget:
    return RollingBudget(
        "g",
        tokens_per_min=10**9,
        requests_per_min=10**6,
        requests_per_day=1000,
        tokens_per_day=200_000,
        store=store,
        daily_window=WINDOW_BUCKET,
        clock=clock,
        sleep=clock.sleep,
    )


def test_bucket_drains_at_limit_per_day(tmp_path: Path) -> None:
    """200,000 tokens/day drain at 2.3148/s; 1,000 requests/day at 0.011574/s."""
    clock = FakeClock(start=START)
    b = _bucket(clock, BudgetStore(tmp_path / "b.json", clock=clock))
    b.record(100_000, 100)
    clock.t += 3600
    req, tok = b.daily_used()
    assert tok == round(100_000 - 200_000 / 86_400 * 3600)  # 91,667
    assert req == round(100 - 1000 / 86_400 * 3600)  # 58
    clock.t += DAY_S
    assert b.daily_used() == (0, 0)


def test_bucket_matches_groq_retry_after(tmp_path: Path) -> None:
    """Balance 197,585 + 2,562 requested over the 200,000 limit: Groq said 63.504 s."""
    clock = FakeClock(start=START)
    b = _bucket(clock, BudgetStore(tmp_path / "b.json", clock=clock))
    b.safety = 1.0
    b.record(197_585, 1)
    fits_at = b.resets_at(2_562, 1).timestamp() - clock()
    assert fits_at == pytest.approx(63.504, abs=0.1)


def test_parse_retry_after_formats() -> None:
    assert parse_retry_after("Please try again in 1m3.504s.") == pytest.approx(63.504)
    assert parse_retry_after("try again in 15m11.088s") == pytest.approx(911.088)
    assert parse_retry_after("try again in 450ms") == pytest.approx(0.45)
    assert parse_retry_after("try again in 1h2m3s") == pytest.approx(3723)
    assert parse_retry_after("no hint") is None
