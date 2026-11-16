"""Throttled, resumable evaluation runner (M08).

run_eval generates answers and computes deterministic scores only; it never calls the
judge (see ragdocs.eval.judge_run and D9). One JSON line per item is appended to
per_question.jsonl as soon as the item finishes, so an interrupted run resumes by
skipping ids already present.
"""

import hashlib
import importlib.metadata
import platform
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from ragdocs.config import REPO_ROOT, Settings, get_settings
from ragdocs.eval.budget_recorder import install_budget_recorder, recorder_active
from ragdocs.eval.scoring import judge_eligible, score_item
from ragdocs.eval.throttle import (
    DailyLimitReached,
    RateLimitPause,
    RollingBudget,
    UsageEstimator,
    default_store,
    groq_budgets,
    is_daily_429,
    log_model_miss,
    parse_retry_after,
    wait_all,
)
from ragdocs.io_utils import append_jsonl, read_json, read_jsonl, write_json
from ragdocs.providers.usage import TokenUsage
from ragdocs.schemas import (
    EvalItem,
    EvalRecord,
    FailedAttempt,
    PipelineResult,
    TokenUsageRecord,
)
from ragdocs.tracing import configure_tracing, flush_traces, traced_run

EXIT_OK = 0
EXIT_PAUSED = 3
PER_QUESTION_FILE = "per_question.jsonl"
# Every failed attempt is appended here at once, so counts survive pauses and resumes.
FAILED_ATTEMPTS_FILE = "failed_attempts.jsonl"
CONFIG_FILE = "config.json"
# config.json keys that must match when resuming into an existing run folder.
RESUME_GUARD_KEYS = (
    "pipeline",
    "eval_set_sha256",
    "index_manifest_hash",
    "tracing_enabled",
    "model_ids",
)
TOOL_PACKAGES = (
    "langchain-core",
    "langchain-groq",
    "langchain-google-genai",
    "langsmith",
    "langgraph",
    "google-genai",
    "groq",
    "pydantic",
    "numpy",
    "rank-bm25",
    "diskcache",
)

Printer = Callable[[str], None]


class EvalSetMismatch(RuntimeError):
    """Raised when the eval set differs from the frozen eval-set-v1 version."""


def sha256_file(path: Path) -> str:
    """Return the sha256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def git_eval_set_unchanged(settings: Settings) -> bool:
    """Return True when `git diff --quiet <tag> -- <eval set>` succeeds."""
    rel = Path(settings.eval_path).resolve().relative_to(REPO_ROOT).as_posix()
    proc = subprocess.run(
        ["git", "diff", "--quiet", settings.eval_set_tag, "--", rel],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return proc.returncode == 0


def check_eval_set(
    settings: Settings,
    git_check: Callable[[Settings], bool] = git_eval_set_unchanged,
) -> str:
    """Refuse unless the eval set hash and git tag check both pass; return the hash."""
    digest = sha256_file(Path(settings.eval_path))
    if digest != settings.eval_set_sha256:
        raise EvalSetMismatch(
            f"eval set sha256 {digest} != frozen {settings.eval_set_sha256} (D15)"
        )
    if not git_check(settings):
        raise EvalSetMismatch(f"git diff {settings.eval_set_tag} -- eval set is not clean (D15)")
    return digest


def load_eval_items(settings: Settings) -> list[EvalItem]:
    """Load the eval set sorted by id."""
    items = [EvalItem.model_validate(r) for r in read_jsonl(settings.eval_path)]
    return sorted(items, key=lambda i: i.id)


def _git(*args: str) -> str:
    """Run a git command in the repo and return stripped stdout ('unknown' on failure)."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return proc.stdout.strip()


def _settings_snapshot(settings: Settings) -> dict[str, Any]:
    """Every Settings value except secrets; paths as repo-relative POSIX strings."""
    snapshot: dict[str, Any] = {}
    for name, field in type(settings).model_fields.items():
        if "SecretStr" in str(field.annotation):
            continue
        value = getattr(settings, name)
        if isinstance(value, SecretStr):
            continue
        if isinstance(value, Path):
            try:
                value = value.resolve().relative_to(REPO_ROOT).as_posix()
            except ValueError:
                value = value.as_posix()
        snapshot[name] = value
    return snapshot


def _tool_versions() -> dict[str, str]:
    """Return installed versions of the packages that affect results."""
    versions = {"python": platform.python_version()}
    for pkg in TOOL_PACKAGES:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "not installed"
    return versions


def build_run_config(
    settings: Settings, pipeline_name: str, eval_sha: str, tracing_active: bool
) -> dict[str, Any]:
    """Return the config.json content for a run."""
    manifest = Path(settings.index_dir) / "manifest.json"
    return {
        "pipeline": pipeline_name,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_ids": {
            "generator_model": settings.generator_model,
            "grader_model": settings.grader_model,
            "judge_model": settings.judge_model,
            "embedding_model": settings.embedding_model,
            "rerank_model": settings.rerank_model,
        },
        "judge_prompt_version": settings.judge_prompt_version,
        "tracing_enabled": tracing_active,
        "langsmith_project": settings.langsmith_project,
        "index_manifest_hash": sha256_file(manifest) if manifest.is_file() else "unknown",
        "eval_set_sha256": eval_sha,
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "tool_versions": _tool_versions(),
        "settings": _settings_snapshot(settings),
    }


def ensure_run_config(run_dir: Path, config: dict[str, Any]) -> None:
    """Write config.json, or check an existing one matches on the resume guard keys."""
    path = run_dir / CONFIG_FILE
    if not path.is_file():
        write_json(path, config)
        return
    existing = read_json(path)
    for key in RESUME_GUARD_KEYS:
        if existing.get(key) != config.get(key):
            raise RuntimeError(
                f"Cannot resume {run_dir}: config.json {key}={existing.get(key)!r} "
                f"differs from current {config.get(key)!r}"
            )


def next_utc_midnight(now: datetime | None = None) -> datetime:
    """Return the next UTC midnight after now."""
    now = now or datetime.now(UTC)
    return datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)


def print_pause(out: Printer, reason: str, remaining: list[str], resets_at: datetime) -> int:
    """Print why the run paused, what remains and when quotas reset; return EXIT_PAUSED."""
    out(f"PAUSED: {reason}")
    out(f"Remaining items ({len(remaining)}): {', '.join(remaining)}")
    out(f"Daily window resets at {resets_at.astimezone(UTC).isoformat()} (UTC).")
    out("Re-run the same command with the same --run-dir to resume.")
    return EXIT_PAUSED


def per_model_usage(usage: TokenUsageRecord) -> dict[str, tuple[int, int]]:
    """Return {model: (tokens_in + tokens_out, calls)} from a usage record."""
    return {m: (u.input_tokens + u.output_tokens, u.calls) for m, u in usage.by_model.items()}


def record_usage(
    budgets: dict[str, RollingBudget], estimator: UsageEstimator, usage: TokenUsageRecord
) -> None:
    """Add one item's usage to each model's budget and to the estimator."""
    per_model = per_model_usage(usage)
    for model, (tokens, calls) in per_model.items():
        if model in budgets:
            budgets[model].record(tokens, calls, persist=not recorder_active())
    estimator.observe(per_model)


def _stream_item(
    pipeline: Any, item: EvalItem, meta: dict[str, Any], usage: TokenUsage
) -> tuple[PipelineResult | None, FailedAttempt | None, str | None]:
    """Run one item inside an eval_item trace; return (result, failure, langsmith run id).

    A failure records the node of the last node_start event before the error (stage).
    """
    with traced_run(
        name="eval_item", run_type="chain", inputs={"question": item.question}, metadata=meta
    ) as run:
        final = None
        stage = "start"
        for event in pipeline.stream(item.question, run_metadata=meta, callbacks=[usage]):
            final = event
            if event.type == "node_start":
                stage = event.node
        if final is None or final.type != "answer":
            error = final.message if final is not None else "pipeline produced no events"
            run.set_error(error)
            utc = datetime.now(UTC).isoformat(timespec="seconds")
            return None, FailedAttempt(stage=stage, message=error, utc=utc), run.run_id
        result = PipelineResult.model_validate(final.data)
        run.set_outputs({"answer": result.answer.text, "abstained": result.answer.abstained})
        return result, None, run.run_id


def build_record(
    item: EvalItem,
    result: PipelineResult,
    usage: TokenUsageRecord,
    run_id: str | None,
    settings: Settings,
    failed: list[FailedAttempt] | None = None,
) -> EvalRecord:
    """Assemble one per_question.jsonl line; failed lists earlier failed attempts."""
    failed = failed or []
    scores = score_item(item, result, usage, settings.eval_context_k)
    rate_limited = [f for f in failed if is_rate_limit(f.message, settings)]
    scores.structured_output_failures = len(failed) - len(rate_limited)
    scores.rate_limited_attempts = len(rate_limited)
    return EvalRecord(
        id=item.id,
        category=item.category,
        question=item.question,
        reference_answer=item.reference_answer,
        evidence=item.evidence,
        must_mention=item.must_mention,
        result=result,
        context_texts=[rc.chunk.text for rc in result.contexts],
        usage=usage,
        langsmith_run_id=run_id,
        scores=scores,
        judge_eligible=judge_eligible(item, result),
        verdict=None,
        failed_attempts=failed,
    )


def is_rate_limit(message: str, settings: Settings) -> bool:
    """True when a failed attempt's message is a provider rate-limit error."""
    return any(message.startswith(p) for p in settings.rate_limit_error_prefixes)


def load_failed_attempts(run_dir: Path, item_id: str) -> list[FailedAttempt]:
    """Return the failed attempts logged for one item in this run folder."""
    path = run_dir / FAILED_ATTEMPTS_FILE
    if not path.is_file():
        return []
    return [
        FailedAttempt.model_validate({k: v for k, v in row.items() if k != "id"})
        for row in read_jsonl(path)
        if row.get("id") == item_id
    ]


def dump_record(record: EvalRecord) -> dict[str, Any]:
    """Serialise a record for JSONL with score aliases (context_hit@5, ...)."""
    return record.model_dump(mode="json", by_alias=True)


def done_ids(path: Path) -> set[str]:
    """Return ids already present in a JSONL file."""
    return {r["id"] for r in read_jsonl(path)} if path.is_file() else set()


def seed_estimator(estimator: UsageEstimator, path: Path) -> None:
    """Feed usage of items already in per_question.jsonl into the estimator."""
    if path.is_file():
        for row in read_jsonl(path):
            estimator.observe(per_model_usage(TokenUsageRecord.model_validate(row["usage"])))


def _run_one(
    item: EvalItem,
    pipeline: Any,
    run_dir: Path,
    settings: Settings,
    budgets: dict[str, RollingBudget],
    estimator: UsageEstimator,
) -> EvalRecord | str:
    """Run one item with retries; return its record or the last error message.

    May raise DailyLimitReached from the budgets.
    """
    meta = {"run": run_dir.name, "item_id": item.id, "category": item.category}
    meta["pipeline"] = pipeline.name
    error = "not attempted"
    attempts = waits = 0
    while attempts < settings.eval_item_attempts:
        wait_all(budgets, estimator)
        usage = TokenUsage()
        result, failure, run_id = _stream_item(pipeline, item, meta, usage)
        usage_record = usage.record()
        record_usage(budgets, estimator, usage_record)
        if result is not None:
            failed = load_failed_attempts(run_dir, item.id)
            return build_record(item, result, usage_record, run_id, settings, failed)
        if failure is None:
            failure = FailedAttempt(stage="unknown", message="unknown error", utc="")
        append_jsonl(run_dir / FAILED_ATTEMPTS_FILE, {"id": item.id, **failure.model_dump()})
        error = failure.message
        if is_rate_limit(error, settings):
            waits += 1
            handle_rate_limit(error, settings, budgets, waits)
            continue  # a rate-limited attempt does not use up an item attempt
        attempts += 1
    return error


def _budget_for(message: str, budgets: dict[str, RollingBudget]) -> RollingBudget | None:
    """Return the budget whose model the 429 message names, else the first one."""
    for model, budget in budgets.items():
        if model in message:
            return budget
    return next(iter(budgets.values()), None)


def handle_rate_limit(
    message: str, settings: Settings, budgets: dict[str, RollingBudget], waits: int
) -> None:
    """429 backstop (D7): sleep for the provider's retry-after, or raise RateLimitPause.

    A per-day 429 while the budget model predicted room is logged as a model miss in
    cache/budget_model_misses.jsonl; at settings.budget_model_max_misses the run pauses.
    """
    budget = _budget_for(message, budgets)
    model = budget.model if budget else "unknown"
    wait = parse_retry_after(message) or settings.rate_limit_default_wait_s
    now = datetime.now(UTC)
    if budget is not None and is_daily_429(message):
        _, tok_cap = budget.daily_caps()
        free = int((tok_cap or 0) - budget.daily_used()[1])
        misses = log_model_miss(Path(settings.cache_dir), model, message, free)
        if misses >= settings.budget_model_max_misses:
            reason = f"budget model missed {misses} times (revert to rolling_24h, D7)"
            raise RateLimitPause(model, reason, now + timedelta(seconds=wait))
    if wait > settings.rate_limit_max_wait_s or waits > settings.rate_limit_max_waits_per_item:
        raise RateLimitPause(model, f"429 retry-after {wait:.0f} s", now + timedelta(seconds=wait))
    sleep = budget.sleep if budget is not None else time.sleep
    sleep(wait + 1.0)


def run_eval(
    pipeline_name: str,
    run_dir: Path,
    *,
    settings: Settings | None = None,
    pipeline: Any = None,
    budgets: dict[str, RollingBudget] | None = None,
    git_check: Callable[[Settings], bool] = git_eval_set_unchanged,
    out: Printer = print,
) -> int:
    """Generate and score every eval item for one pipeline; return an exit code.

    Returns EXIT_OK when all items are done and EXIT_PAUSED (3) on a daily limit or
    an item that still fails after Settings.eval_item_attempts attempts.
    """
    settings = settings or get_settings()
    tracing_active = configure_tracing(settings)
    try:
        eval_sha = check_eval_set(settings, git_check)
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        config = build_run_config(settings, pipeline_name, eval_sha, tracing_active)
        ensure_run_config(run_dir, config)
        return _run_items(pipeline_name, run_dir, settings, pipeline, budgets, out)
    finally:
        flush_traces()


def _run_items(
    pipeline_name: str,
    run_dir: Path,
    settings: Settings,
    pipeline: Any,
    budgets: dict[str, RollingBudget] | None,
    out: Printer,
) -> int:
    """Loop over remaining items in id order, appending one line per finished item."""
    if pipeline is None:
        from ragdocs.pipelines.registry import get_pipeline

        pipeline = get_pipeline(pipeline_name)
    if budgets is None:
        install_budget_recorder(settings)
        budgets = groq_budgets(settings, default_store(settings))
    path = run_dir / PER_QUESTION_FILE
    estimator = UsageEstimator(settings.eval_initial_token_estimate)
    seed_estimator(estimator, path)
    done = done_ids(path)
    remaining = [i for i in load_eval_items(settings) if i.id not in done]
    out(f"{len(done)} items done, {len(remaining)} to run in {run_dir.as_posix()}")
    for idx, item in enumerate(remaining):
        left = [i.id for i in remaining[idx:]]
        try:
            outcome = _run_one(item, pipeline, run_dir, settings, budgets, estimator)
        except DailyLimitReached as exc:
            return print_pause(out, str(exc), left, exc.resets_at)
        if isinstance(outcome, str):
            reason = f"{item.id} failed after {settings.eval_item_attempts} attempts: {outcome}"
            return print_pause(out, reason, left, next_utc_midnight())
        append_jsonl(path, dump_record(outcome))
        out(f"{item.id} done ({outcome.scores.llm_calls} calls, {outcome.scores.latency_ms} ms)")
    from ragdocs.eval.report import write_summary

    write_summary(run_dir)
    out(f"All items done. Summary written to {run_dir.as_posix()}/summary.md")
    return EXIT_OK
