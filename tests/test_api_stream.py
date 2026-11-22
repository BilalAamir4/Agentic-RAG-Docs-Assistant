"""M12 S2 tests: stream runner, POST /api/ask, lifespan, pipeline cache, ChatGroq settings.

No network. Pipelines, limiter, clock and poll are fakes. Time is driven by a fake clock.
"""

import asyncio
import json
import logging
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ragdocs.api import app as app_module
from ragdocs.api.app import app
from ragdocs.api.local import configure_local
from ragdocs.api.ratelimit import LimitResult, rate_limiter_dependency
from ragdocs.api.sse import format_event
from ragdocs.api.stream import MSG_CONFIG, MSG_INTERNAL, MSG_TIMEOUT, StreamRunner
from ragdocs.config import Settings
from ragdocs.providers.llm import get_chat_model
from ragdocs.schemas import Answer, PipelineResult, TraceEvent

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTION = "ZEBRA-QUESTION-9137 how do checkpointers work?"
ANSWER_TEXT = "WOMBAT-ANSWER-4410 uses a checkpointer."
WAIT_S = 2.0  # upper bound for a thread handshake; passing tests never wait this long

SECRETS = {
    "groq_api_key": "g-secret",
    "google_api_key": "k-secret",
    "tavily_api_key": "t-secret",
    "upstash_redis_rest_url": "https://u.example",
    "upstash_redis_rest_token": "u-secret",
    "ip_hash_salt": "fake-salt-0000",
}


def make_settings(**overrides: Any) -> Settings:
    """Settings without .env, with all provider secrets unless overridden."""
    values: dict[str, Any] = {"langsmith_tracing": False, **SECRETS, **overrides}
    return Settings(_env_file=None, **values)


def trace(node: str = "n") -> TraceEvent:
    return TraceEvent(type="node_end", node=node, message=f"{node} done", t_ms=1)


def answer_event(abstained: bool = False, llm_calls: int = 2, used_web: bool = False) -> TraceEvent:
    result = PipelineResult(
        question=QUESTION,
        pipeline="fake",
        answer=Answer(text=ANSWER_TEXT, citations=[], abstained=abstained),
        contexts=[],
        trace=[],
        llm_calls=llm_calls,
        latency_ms=5,
        used_web=used_web,
    )
    return TraceEvent(
        type="answer", node="answer", message="done", data=result.model_dump(), t_ms=2
    )


def error_event(message: str = "Pipeline failed safely.") -> TraceEvent:
    return TraceEvent(type="error", node="x", message=message, t_ms=3)


class FakePipeline:
    """Yields scripted events; optional gates block before event i until set."""

    name = "fake"

    def __init__(self, events: list[TraceEvent], gates: dict[int, threading.Event] | None = None):
        self.events = events
        self.gates = gates or {}
        self.pulled = 0
        self.stopped = threading.Event()
        self.run_metadata: Any = "unset"

    def stream(
        self,
        question: str,
        run_metadata: dict[str, Any] | None = None,
        callbacks: list[Any] | None = None,
    ) -> Iterator[TraceEvent]:
        self.run_metadata = run_metadata
        try:
            for i, event in enumerate(self.events):
                gate = self.gates.get(i)
                if gate is not None:
                    assert gate.wait(WAIT_S)
                self.pulled += 1
                yield event
        finally:
            self.stopped.set()


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def runner_for(pipeline: Any, **kwargs: Any) -> StreamRunner:
    settings = kwargs.pop("settings", None) or make_settings()
    return StreamRunner(
        "baseline", QUESTION, settings, kwargs.pop("load", lambda _name: pipeline),
        kwargs.pop("tracing_active", False), **kwargs,
    )  # fmt: skip


async def collect(runner: StreamRunner, frames: list[str] | None = None) -> list[str]:
    out = frames if frames is not None else []
    async for frame in runner.events():
        out.append(frame)
    return out


def parse(frame: str) -> tuple[str, Any]:
    name, data = frame.rstrip("\n").split("\n", 1)
    return name.removeprefix("event: "), json.loads(data.removeprefix("data: "))


def request_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "ragdocs.api" and r.levelno == logging.INFO
    ]


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    app_module.reset_pipeline_cache()
    yield
    app.dependency_overrides.clear()
    app_module.reset_pipeline_cache()


# ---- runner: frames ----


@pytest.mark.asyncio
async def test_frames_in_order_then_answer() -> None:
    pipe = FakePipeline([trace("a"), trace("b"), answer_event()])
    frames = await collect(runner_for(pipe))
    names = [parse(f)[0] for f in frames]
    assert names == ["trace", "trace", "answer"]
    assert parse(frames[0])[1]["node"] == "a"
    PipelineResult.model_validate(parse(frames[2])[1])
    assert pipe.stopped.wait(WAIT_S)


@pytest.mark.asyncio
async def test_pipeline_error_event_passes_through() -> None:
    frames = await collect(runner_for(FakePipeline([trace(), error_event("Boom, safely.")])))
    assert parse(frames[-1]) == ("error", {"error": "Boom, safely."})
    assert [parse(f)[0] for f in frames] == ["trace", "error"]


@pytest.mark.asyncio
async def test_load_exception_is_internal_error(caplog: pytest.LogCaptureFixture) -> None:
    def load(_name: str) -> Any:
        raise ValueError("detail with ZEBRA-QUESTION-9137")

    caplog.set_level(logging.DEBUG)
    frames = await collect(runner_for(None, load=load))
    assert frames == [format_event("error", {"error": MSG_INTERNAL})]
    assert "ValueError" in caplog.text
    assert "ZEBRA" not in caplog.text


@pytest.mark.asyncio
async def test_missing_key_is_configuration_error() -> None:
    def load(_name: str) -> Any:
        raise RuntimeError("Missing required environment variable: GROQ_API_KEY")

    frames = await collect(runner_for(None, load=load))
    assert [parse(f) for f in frames] == [("error", {"error": MSG_CONFIG})]


@pytest.mark.asyncio
async def test_other_runtime_error_is_internal() -> None:
    def load(_name: str) -> Any:
        raise RuntimeError("something else")

    assert [parse(f)[1] for f in await collect(runner_for(None, load=load))] == [
        {"error": MSG_INTERNAL}
    ]


@pytest.mark.asyncio
async def test_done_without_answer_is_internal_error() -> None:
    frames = await collect(runner_for(FakePipeline([trace("a")])))
    assert [parse(f) for f in frames][-1] == ("error", {"error": MSG_INTERNAL})
    assert len(frames) == 2


@pytest.mark.asyncio
async def test_streaming_exception_is_internal_error() -> None:
    class Boom(FakePipeline):
        def stream(self, question: str, run_metadata: Any = None, callbacks: Any = None) -> Any:
            yield trace("a")
            raise KeyError("x")

    frames = await collect(runner_for(Boom([])))
    assert [parse(f)[0] for f in frames] == ["trace", "error"]


# ---- runner: pings and timeout (fake clock, fake poll) ----


def scripted_poll(clock: FakeClock, steps: list[float], release: threading.Event | None = None):
    """Raise TimeoutError after advancing the clock by each step; then wait on the queue."""
    remaining = list(steps)

    async def poll(queue: asyncio.Queue[Any], timeout: float) -> Any:
        if remaining:
            clock.now += remaining.pop(0)
            raise TimeoutError
        if release is not None:
            release.set()
        return await queue.get()

    return poll


@pytest.mark.asyncio
async def test_ping_only_after_interval() -> None:
    clock = FakeClock()
    gate = threading.Event()
    pipe = FakePipeline([answer_event()], gates={0: gate})
    # 4 s then 6 s: the first empty poll is before the interval (no ping), the second reaches it.
    poll = scripted_poll(clock, [4.0, 6.0], release=gate)
    frames = await collect(runner_for(pipe, clock=clock, poll=poll))
    assert [parse_or_ping(f) for f in frames] == ["ping", "answer"]


def parse_or_ping(frame: str) -> str:
    return "ping" if frame == ": ping\n\n" else parse(frame)[0]


@pytest.mark.asyncio
async def test_no_ping_before_interval() -> None:
    clock = FakeClock()
    gate = threading.Event()
    pipe = FakePipeline([answer_event()], gates={0: gate})
    frames = await collect(runner_for(pipe, clock=clock, poll=scripted_poll(clock, [4.0], gate)))
    assert [parse_or_ping(f) for f in frames] == ["answer"]


@pytest.mark.asyncio
async def test_timeout_error_then_nothing_more(caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeClock()
    gate = threading.Event()  # never set during the run: the pipeline is stuck
    pipe = FakePipeline([answer_event()], gates={0: gate})
    steps = [10.0] * 10
    caplog.set_level(logging.INFO)
    frames = await collect(runner_for(pipe, clock=clock, poll=scripted_poll(clock, steps)))
    assert parse(frames[-1]) == ("error", {"error": MSG_TIMEOUT})
    assert sum(1 for f in frames if f.startswith("event: error")) == 1
    assert clock.now == 50.0  # stopped at request_timeout_s, did not poll again
    assert "outcome=timeout" in request_lines(caplog)[0]
    gate.set()  # let the abandoned worker finish
    assert pipe.stopped.wait(WAIT_S)


# ---- runner: disconnect ----


@pytest.mark.asyncio
async def test_is_disconnected_stops_loop_and_worker(caplog: pytest.LogCaptureFixture) -> None:
    gate = threading.Event()
    pipe = FakePipeline([trace("a"), trace("b"), trace("c"), answer_event()], gates={1: gate})
    calls = 0

    async def disconnected() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    runner = runner_for(pipe, is_disconnected=disconnected)
    caplog.set_level(logging.INFO)
    frames = await collect(runner)
    assert [parse(f)[0] for f in frames] == ["trace"]
    assert runner.cancel_flag.is_set()
    assert "outcome=disconnected" in request_lines(caplog)[0]
    gate.set()
    assert pipe.stopped.wait(WAIT_S)
    assert pipe.pulled == 2  # the in-flight pull finished, nothing after it


@pytest.mark.asyncio
async def test_cancelling_the_iterating_task_sets_cancel_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate = threading.Event()
    pipe = FakePipeline([trace("a"), trace("b"), answer_event()], gates={1: gate})
    runner = runner_for(pipe)
    frames: list[str] = []
    caplog.set_level(logging.INFO)
    task = asyncio.create_task(collect(runner, frames))
    for _ in range(200):
        if frames:
            break
        await asyncio.sleep(0.001)
    assert frames
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert runner.cancel_flag.is_set()
    assert "outcome=disconnected" in request_lines(caplog)[0]
    gate.set()
    assert pipe.stopped.wait(WAIT_S)
    assert pipe.pulled == 2


# ---- runner: run_metadata and trace flush ----


@pytest.mark.asyncio
async def test_run_metadata_only_when_tracing_active() -> None:
    on, off = FakePipeline([answer_event()]), FakePipeline([answer_event()])
    await collect(runner_for(on, tracing_active=True, flush=lambda: None))
    await collect(runner_for(off, tracing_active=False))
    assert on.run_metadata == {"source": "api", "pipeline": "baseline"}
    assert off.run_metadata is None


@pytest.mark.asyncio
async def test_flush_runs_once_after_answer_frame() -> None:
    frames: list[str] = []
    seen: list[int] = []
    runner = runner_for(
        FakePipeline([trace(), answer_event()]),
        tracing_active=True,
        flush=lambda: seen.append(len(frames)),
    )
    await collect(runner, frames)
    assert seen == [2]  # called once, after the answer frame was received


@pytest.mark.asyncio
@pytest.mark.parametrize("events", [[trace(), answer_event()], [trace(), error_event()], [trace()]])
async def test_flush_not_called_when_tracing_inactive_or_no_answer(events: list[Any]) -> None:
    calls: list[int] = []
    await collect(
        runner_for(FakePipeline(events), tracing_active=False, flush=lambda: calls.append(1))
    )
    assert calls == []
    answered = any(e.type == "answer" for e in events)
    await collect(
        runner_for(FakePipeline(events), tracing_active=True, flush=lambda: calls.append(1))
    )
    assert calls == ([1] if answered else [])


@pytest.mark.asyncio
async def test_flush_not_called_after_timeout_or_disconnect() -> None:
    calls: list[int] = []
    clock = FakeClock()
    gate = threading.Event()
    stuck = FakePipeline([answer_event()], gates={0: gate})
    poll = scripted_poll(clock, [10.0] * 10)
    await collect(
        runner_for(
            stuck, clock=clock, poll=poll, tracing_active=True, flush=lambda: calls.append(1)
        )
    )

    async def gone() -> bool:
        return True

    await collect(
        runner_for(FakePipeline([answer_event()]), is_disconnected=gone, tracing_active=True,
                   flush=lambda: calls.append(1))
    )  # fmt: skip
    gate.set()
    assert calls == []


@pytest.mark.asyncio
async def test_raising_flush_does_not_break_stream(caplog: pytest.LogCaptureFixture) -> None:
    def flush() -> None:
        raise ConnectionError("token=abc")

    caplog.set_level(logging.DEBUG)
    frames = await collect(
        runner_for(FakePipeline([answer_event()]), tracing_active=True, flush=flush)
    )
    assert parse(frames[-1])[0] == "answer"
    assert "ConnectionError" in caplog.text
    assert "token=abc" not in caplog.text


@pytest.mark.asyncio
async def test_blocking_flush_times_out(caplog: pytest.LogCaptureFixture) -> None:
    release = threading.Event()
    caplog.set_level(logging.WARNING)
    started = time.monotonic()
    frames = await collect(
        runner_for(
            FakePipeline([answer_event()]),
            settings=make_settings(trace_flush_timeout_s=0.05),
            tracing_active=True,
            flush=lambda: release.wait(WAIT_S),
        )
    )
    release.set()
    assert parse(frames[-1])[0] == "answer"
    assert "trace flush timed out" in caplog.text
    assert time.monotonic() - started < 1.0


# ---- request log lines ----


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("events", "outcome", "calls", "web"),
    [
        ([answer_event(llm_calls=3, used_web=True)], "answer", "3", "true"),
        ([answer_event(abstained=True, llm_calls=1)], "abstained", "1", "false"),
        ([error_event()], "error", "-", "-"),
    ],
)
async def test_one_log_line_per_runner_outcome(
    caplog: pytest.LogCaptureFixture, events: list[Any], outcome: str, calls: str, web: str
) -> None:
    caplog.set_level(logging.DEBUG)
    await collect(runner_for(FakePipeline(events)))
    lines = request_lines(caplog)
    assert len(lines) == 1
    assert lines[0].startswith(f"pipeline=baseline outcome={outcome} latency_ms=")
    assert f"llm_calls={calls} used_web={web} question_chars={len(QUESTION)}" in lines[0]
    assert "ZEBRA" not in caplog.text and "WOMBAT" not in caplog.text


# ---- route through TestClient ----


class FakeLimiter:
    def __init__(self, result: LimitResult | None = None) -> None:
        self.result = result or LimitResult(True, 0, "ok")
        self.calls = 0

    def check(self, client_key: str) -> LimitResult:
        self.calls += 1
        return self.result


def route_client(
    monkeypatch: pytest.MonkeyPatch,
    pipeline: Any = None,
    limiter: FakeLimiter | None = None,
    load: Any = None,
) -> TestClient:
    monkeypatch.setattr(app_module, "get_settings", lambda: make_settings())
    app.dependency_overrides[rate_limiter_dependency] = lambda: limiter or FakeLimiter()
    monkeypatch.setattr(app_module, "get_pipeline", load or (lambda _name: pipeline))
    return TestClient(app, raise_server_exceptions=False)


def test_route_streams_frames_with_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    pipe = FakePipeline([trace("a"), trace("b"), answer_event()])
    client = route_client(monkeypatch, pipe)
    response = client.post("/api/ask", json={"question": QUESTION, "pipeline": "baseline"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    frames = [f + "\n\n" for f in response.text.split("\n\n") if f]
    assert [parse(f)[0] for f in frames] == ["trace", "trace", "answer"]
    PipelineResult.model_validate(parse(frames[-1])[1])


def test_route_log_lines_for_every_outcome(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    body = {"question": QUESTION, "pipeline": "corrective"}
    ok = route_client(monkeypatch, FakePipeline([answer_event()]))
    ok.post("/api/ask", json=body)
    ok.post("/api/ask", json={"question": "ab"})  # invalid
    ok.post("/api/ask", content=b"{not json")  # invalid, no pipeline
    limited = route_client(monkeypatch, limiter=FakeLimiter(LimitResult(False, 30, "ip")))
    limited.post("/api/ask", json=body)
    glob = route_client(monkeypatch, limiter=FakeLimiter(LimitResult(False, 0, "global")))
    glob.post("/api/ask", json=body)
    down = route_client(monkeypatch, limiter=FakeLimiter(LimitResult(False, 0, "unavailable")))
    down.post("/api/ask", json=body)
    lines = request_lines(caplog)
    assert len(lines) == 6
    chars = len(QUESTION)
    assert "pipeline=corrective outcome=answer" in lines[0]
    assert lines[1].startswith("pipeline=self_rag outcome=invalid")
    assert "llm_calls=- used_web=- question_chars=-" in lines[1]
    assert lines[2].startswith("pipeline=- outcome=invalid")
    assert f"question_chars={chars} limit_reason=ip" in lines[3] and "outcome=limited" in lines[3]
    assert lines[4].endswith("limit_reason=global")
    assert lines[5].endswith("limit_reason=unavailable")
    assert "ZEBRA" not in caplog.text and "WOMBAT" not in caplog.text
    assert "testclient" not in caplog.text  # the client host


def test_route_abstained_and_error_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    body = {"question": QUESTION, "pipeline": "baseline"}
    route_client(monkeypatch, FakePipeline([answer_event(abstained=True)])).post(
        "/api/ask", json=body
    )
    route_client(monkeypatch, FakePipeline([error_event()])).post("/api/ask", json=body)
    outcomes = [line.split()[1] for line in request_lines(caplog)]
    assert outcomes == ["outcome=abstained", "outcome=error"]


def test_route_validation_errors_do_not_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = FakeLimiter()
    client = route_client(monkeypatch, FakePipeline([answer_event()]), limiter)
    response = client.post("/api/ask", json={"question": "ab"})
    assert response.status_code == 422
    assert response.json() == {"error": "The question must be between 3 and 500 characters."}
    assert limiter.calls == 0


def test_route_rate_limited_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = route_client(monkeypatch, limiter=FakeLimiter(LimitResult(False, 30, "ip")))
    response = client.post("/api/ask", json={"question": QUESTION})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"


def test_route_missing_key_gives_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "get_settings", lambda: make_settings(groq_api_key=None))
    app.dependency_overrides[rate_limiter_dependency] = lambda: FakeLimiter()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/ask", json={"question": QUESTION, "pipeline": "baseline"})
    assert parse(response.text.strip() + "\n")[1] == {"error": MSG_CONFIG}


# ---- lifespan ----


def test_lifespan_production_error_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = make_settings(env="production", tavily_api_key=None)
    monkeypatch.setattr(app_module, "get_settings", lambda: bad)
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY is missing"):
        with TestClient(app):
            pass


def test_lifespan_local_warns_once_and_sets_tracing_flag(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    bare = make_settings(upstash_redis_rest_url=None, upstash_redis_rest_token=None)
    monkeypatch.setattr(app_module, "get_settings", lambda: bare)
    caplog.set_level(logging.WARNING)
    with TestClient(app) as client:
        assert client.app.state.tracing_active is False  # type: ignore[attr-defined]
    for name in ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        assert caplog.text.count(f"{name} is not set.") == 1


# ---- pipeline cache ----


def test_get_pipeline_builds_once_across_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[str] = []

    def build(name: str) -> Any:
        built.append(name)
        return FakePipeline([answer_event()])

    monkeypatch.setattr(app_module, "get_settings", lambda: make_settings())
    monkeypatch.setattr(app_module.registry, "get_pipeline", build)
    app.dependency_overrides[rate_limiter_dependency] = lambda: FakeLimiter()
    client = TestClient(app)
    for _ in range(2):
        r = client.post("/api/ask", json={"question": QUESTION, "pipeline": "baseline"})
        assert "event: answer" in r.text
    assert built == ["baseline"]


def test_get_pipeline_concurrent_first_requests_build_once(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[str] = []

    def build(name: str) -> Any:
        built.append(name)
        time.sleep(0.02)  # widen the race window
        return FakePipeline([])

    monkeypatch.setattr(app_module, "get_settings", lambda: make_settings())
    monkeypatch.setattr(app_module.registry, "get_pipeline", build)
    results: list[Any] = []
    threads = [
        threading.Thread(target=lambda: results.append(app_module.get_pipeline("self_rag")))
        for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(WAIT_S)
    assert built == ["self_rag"]
    assert results[0] is results[1]


@pytest.mark.parametrize(
    ("name", "missing", "env_name"),
    [
        ("baseline", "groq_api_key", "GROQ_API_KEY"),
        ("baseline", "google_api_key", "GOOGLE_API_KEY"),
        ("corrective", "tavily_api_key", "TAVILY_API_KEY"),
        ("self_rag", "tavily_api_key", "TAVILY_API_KEY"),
    ],
)
def test_get_pipeline_requires_keys(
    monkeypatch: pytest.MonkeyPatch, name: str, missing: str, env_name: str
) -> None:
    monkeypatch.setattr(app_module, "get_settings", lambda: make_settings(**{missing: None}))
    monkeypatch.setattr(app_module.registry, "get_pipeline", lambda n: pytest.fail("built"))
    with pytest.raises(RuntimeError, match=env_name):
        app_module.get_pipeline(name)


def test_get_pipeline_baseline_does_not_need_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "get_settings", lambda: make_settings(tavily_api_key=None))
    monkeypatch.setattr(app_module.registry, "get_pipeline", lambda n: FakePipeline([]))
    assert app_module.get_pipeline("baseline").name == "fake"


# ---- ChatGroq settings ----


def test_chat_model_gets_timeout_and_retries() -> None:
    settings = make_settings(llm_timeout_s=7.0, llm_max_retries=1)
    for role in ("generator", "grader"):
        model = get_chat_model(role, settings)  # type: ignore[arg-type]
        assert model.request_timeout == 7.0  # type: ignore[attr-defined]
        assert model.max_retries == 1  # type: ignore[attr-defined]


def test_llm_max_retries_default_is_the_previous_value() -> None:
    settings = make_settings()
    assert settings.llm_max_retries == 3  # ragdocs.providers.llm passed max_retries=3 before M12
    assert settings.llm_timeout_s == 20.0
    assert settings.trace_flush_timeout_s == 5.0
    assert get_chat_model("generator", settings).max_retries == 3  # type: ignore[attr-defined]


# ---- local server ----


def test_configure_local_serves_files_without_shadowing_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>hello</h1>", encoding="utf-8")
    target = FastAPI()

    @target.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    configure_local(target, tmp_path)
    client = TestClient(target)
    assert "hello" in client.get("/").text
    assert client.get("/api/health").json() == {"status": "ok"}
    cors = client.get("/api/health", headers={"Origin": "http://localhost:8000"})
    assert cors.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert (
        "access-control-allow-origin"
        not in client.get("/api/health", headers={"Origin": "http://evil.example"}).headers
    )


def test_local_app_serves_public_and_keeps_api_routes() -> None:
    script = (
        "from fastapi.testclient import TestClient\n"
        "from ragdocs.api.local import app\n"
        "c = TestClient(app)\n"
        "print(c.get('/').status_code, c.get('/api/health').json()['status'],"
        " c.get('/api/pipelines').status_code)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
        check=True,
    )
    assert out.stdout.split() == ["200", "ok", "200"]


def test_app_never_imports_local() -> None:
    source = (REPO_ROOT / "src" / "ragdocs" / "api" / "app.py").read_text(encoding="utf-8")
    assert "api.local" not in source and "import local" not in source


def test_configure_request_logging_is_idempotent() -> None:
    from ragdocs.api.stream import configure_request_logging, logger

    before = list(logger.handlers)
    configure_request_logging()
    configure_request_logging()
    assert len(logger.handlers) == max(len(before), 1)
    assert logger.isEnabledFor(logging.INFO)


@pytest.mark.asyncio
async def test_worker_inherits_the_callers_context_vars() -> None:
    import contextvars

    marker: contextvars.ContextVar[str] = contextvars.ContextVar("marker", default="unset")
    seen: list[str] = []

    class Peek(FakePipeline):
        def stream(self, question: str, run_metadata: Any = None, callbacks: Any = None) -> Any:
            seen.append(marker.get())
            yield answer_event()

    marker.set("caller")
    await collect(runner_for(Peek([])))
    assert seen == ["caller"]
