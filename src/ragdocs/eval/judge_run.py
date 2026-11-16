"""Resumable judge pass over a stored run (`py tasks.py judge --run-dir DIR`).

Reads per_question.jsonl, judges answerable non-abstained items, and appends
JudgeRecord lines to judge_v<N>.jsonl (N = Settings.judge_prompt_version). Never
modifies per_question.jsonl and never regenerates answers. The same command is the
re-judge path after a prompt version bump (D9).
"""

from pathlib import Path
from typing import Any

from ragdocs.config import Settings, get_settings
from ragdocs.eval.budget_recorder import install_budget_recorder, recorder_active
from ragdocs.eval.judge import (
    cached_verdict,
    judge_file_name,
    judge_item,
    load_records,
    open_judge_cache,
)
from ragdocs.eval.runner import (
    EXIT_OK,
    Printer,
    done_ids,
    next_utc_midnight,
    print_pause,
)
from ragdocs.eval.throttle import (
    DailyLimitReached,
    RollingBudget,
    UsageEstimator,
    default_store,
    judge_budget,
)
from ragdocs.io_utils import append_jsonl, read_jsonl
from ragdocs.pipelines.base import safe_error_message
from ragdocs.providers.usage import TokenUsage
from ragdocs.schemas import EvalRecord, JudgeRecord, JudgeVerdict, TokenUsageRecord
from ragdocs.tracing import configure_tracing, flush_traces, traced_run


def _judge_traced(
    record: EvalRecord,
    run_name: str,
    settings: Settings,
    llm: Any,
    cache: Any,
) -> tuple[JudgeVerdict | None, TokenUsageRecord, str | None]:
    """Judge one record inside a judge_item trace; return (verdict, usage, error)."""
    usage = TokenUsage()
    meta = {
        "run": run_name,
        "item_id": record.id,
        "category": record.category,
        "pipeline": record.result.pipeline,
        "judge_prompt_version": settings.judge_prompt_version,
    }
    with traced_run(
        name="judge_item", run_type="chain", inputs={"question": record.question}, metadata=meta
    ) as run:
        try:
            verdict = judge_item(record, llm=llm, cache=cache, settings=settings, callbacks=[usage])
        except Exception as exc:  # provider and parsing errors are retried, then paused
            message = safe_error_message(exc)
            run.set_error(message)
            return None, usage.record(), message
        run.set_outputs(verdict.model_dump())
    return verdict, usage.record(), None


def _judge_one(
    record: EvalRecord,
    run_name: str,
    settings: Settings,
    deps: tuple[Any, Any, RollingBudget, UsageEstimator],
) -> JudgeRecord | str:
    """Return a JudgeRecord (cached or new) or the last error after all attempts."""
    llm, cache, budget, estimator = deps
    hit = cached_verdict(record, cache, settings)
    if hit is not None:
        return _judge_record(record.id, hit, TokenUsageRecord(), settings, cached=True)
    error = "not attempted"
    for _ in range(settings.eval_item_attempts):
        budget.wait_for(*estimator.estimate(budget.model))
        verdict, usage, err = _judge_traced(record, run_name, settings, llm, cache)
        calls = max(sum(u.calls for u in usage.by_model.values()), 1)
        tokens = usage.tokens_in + usage.tokens_out
        budget.record(tokens, calls, persist=not recorder_active())
        estimator.observe({budget.model: (tokens, calls)})
        if verdict is not None:
            return _judge_record(record.id, verdict, usage, settings, cached=False)
        error = err or "unknown error"
    return error


def _judge_record(
    item_id: str,
    verdict: JudgeVerdict,
    usage: TokenUsageRecord,
    settings: Settings,
    cached: bool,
) -> JudgeRecord:
    """Build one judge_v<N>.jsonl line."""
    return JudgeRecord(
        id=item_id,
        verdict=verdict,
        judge_model=str(settings.judge_model),
        judge_prompt_version=settings.judge_prompt_version,
        usage=usage,
        cached=cached,
    )


def _seed(estimator: UsageEstimator, path: Path, model: str) -> None:
    """Feed usage of already-judged, non-cached items into the estimator."""
    if path.is_file():
        for row in read_jsonl(path):
            rec = JudgeRecord.model_validate(row)
            if not rec.cached:
                calls = max(sum(u.calls for u in rec.usage.by_model.values()), 1)
                estimator.observe({model: (rec.usage.tokens_in + rec.usage.tokens_out, calls)})


def run_judge(
    run_dir: Path,
    *,
    settings: Settings | None = None,
    llm: Any = None,
    budget: RollingBudget | None = None,
    cache: Any = None,
    out: Printer = print,
) -> int:
    """Judge every eligible item of a run not yet in judge_v<N>.jsonl; return exit code."""
    settings = settings or get_settings()
    configure_tracing(settings)
    try:
        return _judge_items(Path(run_dir), settings, llm, budget, cache, out)
    finally:
        flush_traces()


def _judge_items(
    run_dir: Path,
    settings: Settings,
    llm: Any,
    budget: RollingBudget | None,
    cache: Any,
    out: Printer,
) -> int:
    """Loop over eligible records, appending one judge line per finished item."""
    if budget is None:
        install_budget_recorder(settings)
        budget = judge_budget(settings, default_store(settings))
    cache = cache if cache is not None else open_judge_cache(settings)
    path = run_dir / judge_file_name(settings.judge_prompt_version)
    estimator = UsageEstimator(settings.eval_initial_token_estimate)
    _seed(estimator, path, budget.model)
    done = done_ids(path)
    todo = [r for r in load_records(run_dir) if r.judge_eligible and r.id not in done]
    out(f"Judge v{settings.judge_prompt_version}: {len(done)} done, {len(todo)} to judge")
    for idx, record in enumerate(todo):
        left = [r.id for r in todo[idx:]]
        try:
            outcome = _judge_one(record, run_dir.name, settings, (llm, cache, budget, estimator))
        except DailyLimitReached as exc:
            return print_pause(out, str(exc), left, exc.resets_at)
        if isinstance(outcome, str):
            reason = f"{record.id} judge failed after {settings.eval_item_attempts} attempts"
            return print_pause(out, f"{reason}: {outcome}", left, next_utc_midnight())
        append_jsonl(path, outcome.model_dump(mode="json"))
        out(
            f"{record.id} judged: correctness={outcome.verdict.correctness} "
            f"citation_support={outcome.verdict.citation_support} cached={outcome.cached}"
        )
    from ragdocs.eval.report import write_summary

    write_summary(run_dir)
    out(f"Judging complete. Summary written to {run_dir.as_posix()}/summary.md")
    return EXIT_OK
