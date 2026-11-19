"""Per-minute and per-day request and token budgets for free-tier APIs.

Each RollingBudget covers one model. Per-minute limits use a trailing window kept in
memory. Daily usage is stored as timestamped events per model in a JSON file
(cache/budget.json), so separate processes share it. The daily limit is modelled as a
token bucket draining at limit / 24 h (Groq, D7), a rolling 24 hours, or the calendar
day in a time zone (Gemini, D7).
"""

import re
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ragdocs.io_utils import append_jsonl, read_json, read_jsonl, write_json

BUDGET_FILE = "budget.json"
STORE_VERSION = 2
DAY_S = 86400.0
WINDOW_ROLLING = "rolling_24h"
WINDOW_CALENDAR = "calendar_day"
WINDOW_BUCKET = "token_bucket"
WINDOWS = (WINDOW_ROLLING, WINDOW_CALENDAR, WINDOW_BUCKET)


class DailyLimitReached(RuntimeError):
    """Raised when the next call would exceed a model's daily request or token limit."""

    def __init__(self, model: str, kind: str, used: int, limit: int, resets_at: datetime):
        self.model = model
        self.kind = kind
        self.used = used
        self.limit = limit
        self.resets_at = resets_at
        super().__init__(
            f"Daily {kind} limit for {model} reached ({used}/{limit}); "
            f"enough frees at {resets_at.astimezone(UTC).isoformat()}"
        )


def _migrate_legacy(data: dict[str, Any], now: float) -> dict[str, list[list[float]]]:
    """Convert the v1 format {model: {"date", "requests", "tokens"}} to events.

    Each day's total becomes one event at the end of that UTC date (capped at now),
    the latest time the usage could have happened, so it never expires too early.
    """
    events: dict[str, list[list[float]]] = {}
    for model, entry in data.items():
        if not isinstance(entry, dict) or "date" not in entry:
            continue
        day_end = datetime.fromisoformat(entry["date"]).replace(tzinfo=UTC) + timedelta(days=1)
        t = min(day_end.timestamp(), now)
        events[model] = [[t, int(entry.get("requests", 0)), int(entry.get("tokens", 0))]]
    return events


class BudgetStore:
    """Timestamped usage events per model: {"version": 2, "events": {model: [[t, req, tok]]}}.

    With path None the events live in memory only. Events older than retention_s are
    dropped on every write.
    """

    def __init__(
        self,
        path: Path | None,
        *,
        retention_s: float = 2 * DAY_S,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.retention_s = retention_s
        self.clock = clock
        self._mem: dict[str, list[list[float]]] = {}
        self._lock = threading.Lock()

    def _load(self) -> dict[str, list[list[float]]]:
        """Return all events, migrating the v1 format if found."""
        if self.path is None:
            return {m: [list(e) for e in evs] for m, evs in self._mem.items()}
        if not self.path.is_file():
            return {}
        data = read_json(self.path)
        if not isinstance(data, dict):
            return {}
        if data.get("version") == STORE_VERSION:
            return {m: [list(e) for e in evs] for m, evs in data.get("events", {}).items()}
        return _migrate_legacy(data, self.clock())

    def _save(self, events: dict[str, list[list[float]]]) -> None:
        if self.path is None:
            self._mem = events
        else:
            write_json(self.path, {"version": STORE_VERSION, "events": events})

    def add(self, model: str, requests: int, tokens: int, t: float | None = None) -> None:
        """Append one usage event for model (at t, default now) and prune old events."""
        with self._lock:
            events = self._load()
            cutoff = self.clock() - self.retention_s
            events = {m: [e for e in evs if e[0] > cutoff] for m, evs in events.items()}
            stamp = self.clock() if t is None else t
            events.setdefault(model, []).append([round(stamp, 3), int(requests), int(tokens)])
            events[model].sort(key=lambda e: e[0])
            self._save(events)

    def events(self, model: str, since: float) -> list[tuple[float, int, int]]:
        """Return (t, requests, tokens) events for model after since, oldest first."""
        evs = self._load().get(model, [])
        return [(float(t), int(r), int(k)) for t, r, k in evs if t > since]

    def used_since(self, model: str, since: float) -> tuple[int, int]:
        """Return (requests, tokens) recorded for model after since."""
        evs = self.events(model, since)
        return sum(e[1] for e in evs), sum(e[2] for e in evs)

    def models(self) -> list[str]:
        """Return every model with stored events."""
        return sorted(self._load())


@dataclass
class _Event:
    t: float
    tokens: int
    requests: int


class RollingBudget:
    """Throttle one model to per-minute and per-day request and token limits.

    wait_for sleeps until the trailing minute plus the estimate fits within
    limit x safety, and raises DailyLimitReached if the daily window's usage plus the
    estimate would exceed daily limit x safety. record adds actual usage after a call.
    """

    def __init__(
        self,
        model: str,
        tokens_per_min: int,
        requests_per_min: int,
        requests_per_day: int,
        tokens_per_day: int | None = None,
        *,
        safety: float = 0.9,
        store: BudgetStore | None = None,
        timezone: str = "UTC",
        daily_window: str = WINDOW_CALENDAR,
        window_s: float = 60.0,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if daily_window not in WINDOWS:
            raise ValueError(f"Unknown daily_window {daily_window!r}")
        self.model = model
        self.tokens_per_min = tokens_per_min
        self.requests_per_min = requests_per_min
        self.requests_per_day = requests_per_day
        self.tokens_per_day = tokens_per_day
        self.safety = safety
        self.store = store if store is not None else BudgetStore(None, clock=clock)
        self.tz = ZoneInfo(timezone)
        self.daily_window = daily_window
        self.window_s = window_s
        self.clock = clock
        self.sleep = sleep
        self._events: deque[_Event] = deque()

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), tz=self.tz)

    def day(self) -> str:
        """Return the current calendar day as YYYY-MM-DD in the budget's time zone."""
        return self._now().date().isoformat()

    def window_start(self) -> float:
        """Return the epoch time where the daily window starts (bucket: retention start)."""
        if self.daily_window == WINDOW_BUCKET:
            return self.clock() - self.store.retention_s
        if self.daily_window == WINDOW_ROLLING:
            return self.clock() - DAY_S
        now = self._now()
        return datetime.combine(now.date(), datetime.min.time(), self.tz).timestamp()

    def daily_used(self) -> tuple[int, int]:
        """Return (requests, tokens) used in the daily window (bucket: current balance)."""
        if self.daily_window == WINDOW_BUCKET:
            req, tok = self._bucket_balance()
            return int(round(req)), int(round(tok))
        return self.store.used_since(self.model, self.window_start())

    def drain_rates(self) -> tuple[float, float]:
        """Return (requests, tokens) per second the bucket drains: daily limit / 24 h."""
        return self.requests_per_day / DAY_S, (self.tokens_per_day or 0) / DAY_S

    def _bucket_balance(self) -> tuple[float, float]:
        """Replay stored events: each adds to the balance, which drains continuously."""
        r_req, r_tok = self.drain_rates()
        req = tok = 0.0
        prev = None
        for t, n_req, n_tok in self.store.events(self.model, self.window_start()):
            if prev is not None:
                req, tok = max(0.0, req - r_req * (t - prev)), max(0.0, tok - r_tok * (t - prev))
            req, tok, prev = req + n_req, tok + n_tok, t
        if prev is not None:
            dt = max(0.0, self.clock() - prev)
            req, tok = max(0.0, req - r_req * dt), max(0.0, tok - r_tok * dt)
        return req, tok

    def daily_caps(self) -> tuple[float, float | None]:
        """Return (request cap, token cap) = daily limits x safety."""
        tpd = self.tokens_per_day
        return self.requests_per_day * self.safety, (tpd * self.safety if tpd else None)

    def resets_at(self, est_tokens: int = 0, est_requests: int = 0) -> datetime:
        """Return when the estimate first fits the daily caps.

        Calendar windows reset at the next local midnight. Rolling windows free usage
        as events pass 24 hours; this walks the events oldest first. A bucket frees
        usage continuously at the drain rate.
        """
        now = self._now()
        if self.daily_window == WINDOW_BUCKET:
            return self._bucket_fits_at(est_tokens, est_requests)
        if self.daily_window == WINDOW_CALENDAR:
            return datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), self.tz)
        req_cap, tok_cap = self.daily_caps()
        requests, tokens = self.daily_used()
        free_at = self.clock()
        for t, req, tok in self.store.events(self.model, self.window_start()):
            fits_tokens = tok_cap is None or tokens + est_tokens <= tok_cap
            if requests + est_requests <= req_cap and fits_tokens:
                break
            requests, tokens = requests - req, tokens - tok
            free_at = t + DAY_S
        return datetime.fromtimestamp(free_at, tz=UTC)

    def _bucket_fits_at(self, est_tokens: int, est_requests: int) -> datetime:
        """Return when the bucket balance plus the estimate first fits the caps."""
        req, tok = self._bucket_balance()
        req_cap, tok_cap = self.daily_caps()
        r_req, r_tok = self.drain_rates()
        wait = max(0.0, (req + est_requests - req_cap) / r_req) if r_req else 0.0
        if tok_cap is not None and r_tok:
            wait = max(wait, (tok + est_tokens - tok_cap) / r_tok)
        return datetime.fromtimestamp(self.clock() + wait, tz=UTC)

    def _check_daily(self, est_tokens: int, est_requests: int) -> None:
        """Raise DailyLimitReached if window usage plus the estimate exceeds a cap.

        The safety margin covers usage the counters miss (for example provider-side
        accounting that differs from reported usage).
        """
        requests, tokens = self.daily_used()
        req_cap, tok_cap = self.daily_caps()
        if requests + est_requests > req_cap:
            raise DailyLimitReached(
                self.model,
                "requests",
                requests,
                self.requests_per_day,
                self.resets_at(est_tokens, est_requests),
            )
        if tok_cap is not None and tokens + est_tokens > tok_cap:
            raise DailyLimitReached(
                self.model,
                "tokens",
                tokens,
                int(self.tokens_per_day or 0),
                self.resets_at(est_tokens, est_requests),
            )

    def _window(self) -> tuple[int, int]:
        """Drop events older than the window and return (tokens, requests) inside it."""
        cutoff = self.clock() - self.window_s
        while self._events and self._events[0].t <= cutoff:
            self._events.popleft()
        return sum(e.tokens for e in self._events), sum(e.requests for e in self._events)

    def wait_for(self, est_tokens: int, est_requests: int) -> float:
        """Block until the estimate fits the per-minute limits; return seconds slept."""
        self._check_daily(est_tokens, est_requests)
        token_cap = self.tokens_per_min * self.safety
        request_cap = self.requests_per_min * self.safety
        slept = 0.0
        while True:
            tokens, requests = self._window()
            fits = tokens + est_tokens <= token_cap and requests + est_requests <= request_cap
            if fits or not self._events:
                return slept
            delay = max(self._events[0].t + self.window_s - self.clock(), 0.0) + 0.01
            self.sleep(delay)
            slept += delay

    def record(self, tokens: int, requests: int, *, persist: bool = True) -> None:
        """Record usage in the per-minute window and, if persist, in the store.

        persist is False when a BudgetRecorder already writes every call to the store.
        """
        self._events.append(_Event(self.clock(), tokens, requests))
        if persist:
            self.store.add(self.model, requests, tokens, t=self.clock())


class UsageEstimator:
    """Estimate the next item's per-model usage as the maximum observed so far.

    Before any observation the token estimate is `initial_tokens` and the request
    estimate is `initial_requests` for every model.
    """

    def __init__(self, initial_tokens: int, initial_requests: int = 1) -> None:
        self.initial_tokens = initial_tokens
        self.initial_requests = initial_requests
        self._observed = False
        self._max: dict[str, tuple[int, int]] = {}

    def estimate(self, model: str) -> tuple[int, int]:
        """Return (tokens, requests) expected for model on the next item."""
        if not self._observed:
            return self.initial_tokens, self.initial_requests
        return self._max.get(model, (0, 0))

    def observe(self, per_model: dict[str, tuple[int, int]]) -> None:
        """Update maxima with one item's (tokens, requests) per model."""
        self._observed = True
        for model, (tokens, requests) in per_model.items():
            old_t, old_r = self._max.get(model, (0, 0))
            self._max[model] = (max(old_t, tokens), max(old_r, requests))


def default_store(settings: Any) -> BudgetStore:
    """Return the shared BudgetStore at <cache_dir>/budget.json."""
    return BudgetStore(Path(settings.cache_dir) / BUDGET_FILE)


def groq_budgets(settings: Any, store: BudgetStore | None) -> dict[str, RollingBudget]:
    """Return one RollingBudget per Groq model listed in settings.groq_rpd_limit."""
    return {
        model: RollingBudget(
            model,
            tokens_per_min=settings.groq_tpm_limit,
            requests_per_min=settings.groq_rpm_limit,
            requests_per_day=rpd,
            tokens_per_day=settings.groq_tpd_limit.get(model),
            safety=settings.throttle_safety,
            store=store,
            timezone=settings.groq_quota_timezone,
            daily_window=settings.groq_quota_window,
            window_s=settings.throttle_window_s,
        )
        for model, rpd in settings.groq_rpd_limit.items()
    }


def judge_budget(settings: Any, store: BudgetStore | None) -> RollingBudget:
    """Return the RollingBudget for settings.judge_model (calendar day, Pacific)."""
    return RollingBudget(
        str(settings.judge_model),
        tokens_per_min=settings.judge_tpm_limit,
        requests_per_min=settings.judge_rpm_limit,
        requests_per_day=settings.judge_rpd_limit,
        safety=settings.throttle_safety,
        store=store,
        timezone=settings.judge_quota_timezone,
        window_s=settings.throttle_window_s,
    )


def embedding_budget(settings: Any, store: BudgetStore | None) -> RollingBudget:
    """Return the RollingBudget for settings.embedding_model (calendar day, Pacific)."""
    return RollingBudget(
        str(settings.embedding_model),
        tokens_per_min=settings.embedding_tpm_limit,
        requests_per_min=settings.embedding_rpm_limit,
        requests_per_day=settings.embedding_rpd_limit,
        safety=settings.throttle_safety,
        store=store,
        timezone=settings.embedding_quota_timezone,
        window_s=settings.throttle_window_s,
    )


def ragas_llm_budget(settings: Any, store: BudgetStore | None) -> RollingBudget:
    """Return the RollingBudget for settings.ragas_llm_model (calendar day, Pacific)."""
    return RollingBudget(
        str(settings.ragas_llm_model),
        tokens_per_min=settings.ragas_llm_tpm_limit,
        requests_per_min=settings.ragas_llm_rpm_limit,
        requests_per_day=settings.ragas_llm_rpd_limit,
        safety=settings.throttle_safety,
        store=store,
        timezone=settings.ragas_llm_quota_timezone,
        window_s=settings.throttle_window_s,
    )


def all_budgets(settings: Any, store: BudgetStore | None) -> dict[str, RollingBudget]:
    """Return budgets for every model with configured limits (Groq, judge, RAGAS, embedding)."""
    budgets = groq_budgets(settings, store)
    if settings.judge_model:
        budgets[str(settings.judge_model)] = judge_budget(settings, store)
    if settings.ragas_llm_model:
        budgets[str(settings.ragas_llm_model)] = ragas_llm_budget(settings, store)
    if settings.embedding_model:
        budgets[str(settings.embedding_model)] = embedding_budget(settings, store)
    return budgets


def wait_all(budgets: dict[str, RollingBudget], estimator: UsageEstimator) -> None:
    """Wait on every budget with its model's estimate; may raise DailyLimitReached."""
    for model, budget in budgets.items():
        tokens, requests = estimator.estimate(model)
        budget.wait_for(tokens, requests)


MISSES_FILE = "budget_model_misses.jsonl"
_RETRY_RE = re.compile(r"try again in ([0-9hms.]+)", re.IGNORECASE)
_PART_RE = re.compile(r"([0-9.]+)(ms|h|m|s)")
_UNIT_S = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
DAILY_429_MARKERS = ("per day", "(TPD)", "(RPD)")


class RateLimitPause(DailyLimitReached):
    """Raised to pause a run after a provider 429 (backstop or budget-model miss)."""

    def __init__(self, model: str, reason: str, resets_at: datetime):
        RuntimeError.__init__(
            self, f"{reason} for {model}; retry at {resets_at.astimezone(UTC).isoformat()}"
        )
        self.model, self.kind, self.used, self.limit = model, "rate_limit", 0, 0
        self.resets_at = resets_at


def parse_retry_after(message: str) -> float | None:
    """Return seconds from a 'try again in 1m3.504s' / '450ms' hint, or None."""
    match = _RETRY_RE.search(message)
    if not match:
        return None
    parts = _PART_RE.findall(match.group(1))
    return sum(float(n) * _UNIT_S[u] for n, u in parts) if parts else None


def is_daily_429(message: str) -> bool:
    """True when a 429 message names a per-day limit (TPD or RPD)."""
    return any(m in message for m in DAILY_429_MARKERS)


def log_model_miss(cache_dir: Path, model: str, message: str, predicted_free: int) -> int:
    """Append one budget-model miss to cache/budget_model_misses.jsonl; return the count."""
    path = Path(cache_dir) / MISSES_FILE
    append_jsonl(
        path,
        {
            "utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": model,
            "predicted_free_tokens_at_safety": predicted_free,
            "message": message[:400],
        },
    )
    return len(read_jsonl(path))
