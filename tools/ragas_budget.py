"""Standard-library budget store and throttle for tools/ragas_score.py (D7, D24).

Purpose: let the isolated RAGAS scorer (.venv-ragas, no ragdocs imports) read and write
cache/budget.json in exactly the format ragdocs.eval.throttle.BudgetStore uses, check
per-minute and per-day limits before calls, and record every call.

Inputs: the path of cache/budget.json and the limits passed on the scorer's command line.
Outputs: updated cache/budget.json. Raises DailyLimitReached when a daily cap would be
exceeded (the scorer exits with code 3).

File contract (D24): {"version": 2, "events": {model: [[t, requests, tokens], ...]}},
t = epoch seconds rounded to 3 decimals, requests and tokens integers, events sorted by
t, events older than 2 days dropped on every write; JSON with indent 2, UTF-8, LF and a
trailing newline. One process writes the file at a time.
"""

import json
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

STORE_VERSION = 2
DAY_S = 86_400.0
RETENTION_S = 2 * DAY_S


class DailyLimitReached(RuntimeError):
    """Raised when the next call would exceed a model's daily request or token cap."""

    def __init__(self, model: str, kind: str, used: int, limit: int, resets_at: datetime):
        self.model, self.kind, self.used, self.limit = model, kind, used, limit
        self.resets_at = resets_at
        super().__init__(
            f"Daily {kind} limit for {model} reached ({used}/{limit}); "
            f"enough frees at {resets_at.astimezone(UTC).isoformat()}"
        )


class BudgetFile:
    """Read and append per-call events in the v2 budget file."""

    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self.clock = clock

    def load(self) -> dict[str, list[list[float]]]:
        """Return all events; refuse any format other than version 2."""
        if not self.path.is_file():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != STORE_VERSION:
            raise ValueError(
                f"{self.path} is not a version-2 budget file; run `py tasks.py budget` "
                "in the main venv once to migrate it"
            )
        return {m: [list(e) for e in evs] for m, evs in data.get("events", {}).items()}

    def save(self, events: dict[str, list[list[float]]]) -> None:
        """Write events in the contract format (indent 2, UTF-8, LF, trailing newline)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            {"version": STORE_VERSION, "events": events}, ensure_ascii=False, indent=2
        )
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")

    def add(self, model: str, requests: int, tokens: int, t: float | None = None) -> None:
        """Append one event for model (at t, default now) and prune events over 2 days old."""
        events = self.load()
        cutoff = self.clock() - RETENTION_S
        events = {m: [e for e in evs if e[0] > cutoff] for m, evs in events.items()}
        stamp = self.clock() if t is None else t
        events.setdefault(model, []).append([round(stamp, 3), int(requests), int(tokens)])
        events[model].sort(key=lambda e: e[0])
        self.save(events)

    def used_since(self, model: str, since: float) -> tuple[int, int]:
        """Return (requests, tokens) recorded for model after since."""
        evs = [e for e in self.load().get(model, []) if e[0] > since]
        return sum(int(e[1]) for e in evs), sum(int(e[2]) for e in evs)


class CalendarBudget:
    """Per-minute throttle and calendar-day cap for one model (same rules as RollingBudget).

    Daily usage is everything recorded since local midnight in the model's time zone;
    caps are limit x safety. The per-minute window holds this process's calls only.
    """

    def __init__(
        self,
        model: str,
        store: BudgetFile,
        *,
        requests_per_min: int,
        tokens_per_min: int,
        requests_per_day: int,
        safety: float,
        timezone: str,
        window_s: float = 60.0,
        rpm_ceiling: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model, self.store = model, store
        self.rpm, self.tpm, self.rpd = requests_per_min, tokens_per_min, requests_per_day
        self.safety, self.tz, self.window_s = safety, ZoneInfo(timezone), window_s
        # Requests allowed per window: rpm x safety, lowered to rpm_ceiling when given.
        cap = requests_per_min * safety
        self.minute_cap = min(cap, rpm_ceiling) if rpm_ceiling else cap
        self.sleep = sleep
        self._minute: deque[tuple[float, int, int]] = deque()

    def window_start(self) -> float:
        """Epoch time of the current local midnight."""
        now = datetime.fromtimestamp(self.store.clock(), tz=self.tz)
        return datetime.combine(now.date(), datetime.min.time(), self.tz).timestamp()

    def resets_at(self) -> datetime:
        """Next local midnight."""
        now = datetime.fromtimestamp(self.store.clock(), tz=self.tz)
        return datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), self.tz)

    def daily_used(self) -> tuple[int, int]:
        """(requests, tokens) used today."""
        return self.store.used_since(self.model, self.window_start())

    def check_daily(self, est_requests: int) -> None:
        """Raise DailyLimitReached if today's requests plus the estimate exceed the cap."""
        used, _ = self.daily_used()
        if used + est_requests > self.rpd * self.safety:
            raise DailyLimitReached(self.model, "requests", used, self.rpd, self.resets_at())

    def throttle(self, est_tokens: int) -> float:
        """Before one call: sleep until one more request fits the minute window (no daily check)."""
        return self._wait_minute(est_tokens, 1)

    def wait_for(self, est_tokens: int, est_requests: int) -> float:
        """Check the daily cap, then sleep until the estimate fits the minute window."""
        self.check_daily(est_requests)
        return self._wait_minute(est_tokens, est_requests)

    def _wait_minute(self, est_tokens: int, est_requests: int) -> float:
        """Sleep until est_requests and est_tokens fit the per-minute window."""
        slept = 0.0
        while True:
            cutoff = self.store.clock() - self.window_s
            while self._minute and self._minute[0][0] <= cutoff:
                self._minute.popleft()
            req = sum(e[1] for e in self._minute)
            tok = sum(e[2] for e in self._minute)
            fits = req + est_requests <= self.minute_cap
            fits = fits and tok + est_tokens <= self.tpm * self.safety
            if fits or not self._minute:
                return slept
            delay = max(self._minute[0][0] + self.window_s - self.store.clock(), 0.0) + 0.01
            self.sleep(delay)
            slept += delay

    def record(self, requests: int, tokens: int) -> None:
        """Record one call in the minute window and the budget file."""
        t = self.store.clock()
        self._minute.append((t, requests, tokens))
        self.store.add(self.model, requests, tokens, t=t)
