"""M12 S1 tests: SSE, rate limiter, startup validation, request validation, pipelines list."""

import importlib.util
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from ragdocs.api import ratelimit
from ragdocs.api.app import app
from ragdocs.api.preflight import ask_preflight, body_size_guard
from ragdocs.api.ratelimit import (
    DisabledRateLimiter,
    LimitResult,
    UpstashRateLimiter,
    client_ip,
    client_key,
    get_rate_limiter,
    rate_limiter_dependency,
)
from ragdocs.api.sse import SSE_HEADERS, format_event, ping
from ragdocs.api.startup import validate_runtime_settings
from ragdocs.config import Settings
from ragdocs.pipelines.registry import list_pipelines

SECRETS = {
    "groq_api_key": "g-secret",
    "google_api_key": "k-secret",
    "tavily_api_key": "t-secret",
    "upstash_redis_rest_url": "https://example.upstash.io",
    "upstash_redis_rest_token": "u-secret",
}


def make_settings(**overrides: Any) -> Settings:
    """Settings without .env, with all production secrets unless overridden."""
    values: dict[str, Any] = {"langsmith_tracing": False, **SECRETS, **overrides}
    return Settings(_env_file=None, **values)


# ---- sse ----


def test_format_event_exact_and_ping() -> None:
    out = format_event("trace", {"a": 1, "b": [1, 2]})
    assert out == 'event: trace\ndata: {"a":1,"b":[1,2]}\n\n'
    assert ping() == ": ping\n\n"


def test_format_event_single_line_roundtrip() -> None:
    payload = {"text": "line1\nline2 é 日本"}
    out = format_event("answer", payload)
    assert out.count("\n") == 3
    data_line = out.split("\n")[1]
    assert data_line.startswith("data: ")
    assert json.loads(data_line[6:]) == payload
    assert "é 日本" in out


def test_format_event_rejects_newline_in_name() -> None:
    with pytest.raises(ValueError):
        format_event("a\nb", {})


def test_sse_headers() -> None:
    assert "no-cache" in SSE_HEADERS["Cache-Control"]
    assert SSE_HEADERS["X-Accel-Buffering"] == "no"


# ---- client key and ip ----


def test_client_key() -> None:
    a = client_key("1.2.3.4", "salt")
    assert a == client_key("1.2.3.4", "salt")
    assert len(a) == 16 and int(a, 16) >= 0
    assert a != client_key("1.2.3.4", None)
    assert client_key("1.2.3.4", None) == client_key("1.2.3.4", "")


def _request(headers: dict[str, str], host: str | None) -> Any:
    client = SimpleNamespace(host=host) if host else None
    return SimpleNamespace(headers={k.lower(): v for k, v in headers.items()}, client=client)


def test_client_ip_order() -> None:
    assert client_ip(_request({"X-Forwarded-For": " 9.9.9.9 , 1.1.1.1"}, "2.2.2.2")) == "9.9.9.9"
    assert client_ip(_request({}, "2.2.2.2")) == "2.2.2.2"
    assert client_ip(_request({}, None)) == "unknown"


# ---- Upstash limiter with fakes ----


class FakeRedis:
    def __init__(self, count: int = 1, fail: bool = False) -> None:
        self.count, self.fail = count, fail
        self.incr_calls: list[str] = []
        self.expire_calls: list[tuple[str, int]] = []

    def incr(self, key: str) -> int:
        if self.fail:
            raise ConnectionError("boom 1.2.3.4 token")
        self.incr_calls.append(key)
        return self.count

    def expire(self, key: str, seconds: int) -> int:
        self.expire_calls.append((key, seconds))
        return 1


class FakeIpLimiter:
    def __init__(self, allowed: bool = True, reset: float = 0.0) -> None:
        self.allowed, self.reset = allowed, reset
        self.keys: list[str] = []

    def limit(self, key: str) -> Any:
        self.keys.append(key)
        return SimpleNamespace(allowed=self.allowed, reset=self.reset)


NOON = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC).timestamp()


def make_limiter(redis: FakeRedis, ip: FakeIpLimiter, cap: int = 3) -> UpstashRateLimiter:
    return UpstashRateLimiter(
        make_settings(daily_global_cap=cap), redis=redis, ip_limiter=ip, clock=lambda: NOON
    )


def test_limiter_allowed_sets_expire_only_on_first() -> None:
    redis = FakeRedis(count=1)
    result = make_limiter(redis, FakeIpLimiter()).check("k")
    assert result == LimitResult(True, 0, "ok")
    assert redis.incr_calls == ["ragdocs:global:20261122"]
    assert redis.expire_calls == [("ragdocs:global:20261122", 172800)]
    redis2 = FakeRedis(count=2)
    make_limiter(redis2, FakeIpLimiter()).check("k")
    assert redis2.expire_calls == []


def test_limiter_ip_denied_skips_global() -> None:
    redis = FakeRedis()
    result = make_limiter(redis, FakeIpLimiter(False, NOON + 90.2)).check("k")
    assert result == LimitResult(False, 91, "ip")
    assert redis.incr_calls == []
    assert make_limiter(redis, FakeIpLimiter(False, NOON - 5)).check("k").retry_after_s == 1


def test_limiter_global_over_cap() -> None:
    result = make_limiter(FakeRedis(count=4), FakeIpLimiter(), cap=3).check("k")
    assert result == LimitResult(False, 12 * 3600, "global")
    assert make_limiter(FakeRedis(count=3), FakeIpLimiter(), cap=3).check("k").allowed


def test_limiter_unavailable_logs_class_only(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = make_limiter(FakeRedis(fail=True), FakeIpLimiter()).check("abcd1234key")
    assert result == LimitResult(False, 0, "unavailable")
    assert len(caplog.records) == 1
    text = caplog.text
    assert "ConnectionError" in text
    assert "1.2.3.4" not in text and "abcd1234key" not in text and "token" not in text


def test_get_rate_limiter_disabled_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    ratelimit.reset_rate_limiter_state()
    bare = Settings(_env_file=None, env="local")
    with caplog.at_level(logging.WARNING):
        first, second = get_rate_limiter(bare), get_rate_limiter(bare)
    assert isinstance(first, DisabledRateLimiter) and isinstance(second, DisabledRateLimiter)
    assert len([r for r in caplog.records if "disabled" in r.getMessage()]) == 1
    assert first.check("x").allowed
    ratelimit.reset_rate_limiter_state()


def test_get_rate_limiter_production_without_upstash_raises() -> None:
    ratelimit.reset_rate_limiter_state()
    with pytest.raises(RuntimeError, match="UPSTASH"):
        get_rate_limiter(Settings(_env_file=None, env="production"))


def test_get_rate_limiter_builds_upstash_without_network() -> None:
    assert isinstance(get_rate_limiter(make_settings()), UpstashRateLimiter)


# ---- startup validation ----


@pytest.mark.parametrize("name", list(SECRETS))
def test_production_requires_each_secret(name: str) -> None:
    with pytest.raises(RuntimeError) as err:
        validate_runtime_settings(make_settings(env="production", **{name: None}))
    assert name.upper() in str(err.value)
    assert "-secret" not in str(err.value)


def test_production_tracing_sampling() -> None:
    bad = make_settings(env="production", langsmith_tracing=True, langsmith_sampling_rate=0.5)
    with pytest.raises(RuntimeError, match="SAMPLING_RATE"):
        validate_runtime_settings(bad)
    ok = make_settings(env="production", langsmith_tracing=True, langsmith_sampling_rate=0.1)
    validate_runtime_settings(ok)


def test_production_ok_and_cohere_not_required() -> None:
    validate_runtime_settings(make_settings(env="production", use_reranker=False))


def test_local_never_raises_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    bare = Settings(_env_file=None, env="local", langsmith_tracing=True)
    with caplog.at_level(logging.WARNING):
        validate_runtime_settings(bare)
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 5
    assert any("UPSTASH_REDIS_REST_URL" in m for m in messages)
    assert not any("COHERE" in m for m in messages)


# ---- request validation through a stub route ----


class CountingLimiter:
    def __init__(self, result: LimitResult | None = None) -> None:
        self.result = result or LimitResult(True, 0, "ok")
        self.calls = 0

    def check(self, client_key: str) -> LimitResult:
        self.calls += 1
        return self.result


def make_client(limiter: CountingLimiter, settings: Settings) -> TestClient:
    stub = FastAPI()
    stub.exception_handlers.update(app.exception_handlers)

    @stub.post("/stub", dependencies=[Depends(body_size_guard)])
    async def stub_route(request: Request) -> JSONResponse:
        outcome = ask_preflight(request, await request.body(), limiter, settings)
        if isinstance(outcome, JSONResponse):
            return outcome
        return JSONResponse({"ok": True, "question": outcome[0], "pipeline": outcome[1]})

    @stub.get("/boom")
    async def boom() -> None:
        raise ValueError("secret-detail")

    return TestClient(stub, raise_server_exceptions=False)


LEN_MSG = "The question must be between 3 and 500 characters."
BAD_MSG = 'Send JSON with a "question" string.'
CTRL_MSG = "The question contains unsupported control characters."
PIPE_MSG = "Unknown pipeline. Choose baseline, corrective or self_rag."


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not json", BAD_MSG),
        (b"[1,2]", BAD_MSG),
        (b"{}", BAD_MSG),
        (b'{"question": 5}', BAD_MSG),
        (b'{"question": "ab"}', LEN_MSG),
        (b'{"question": "   a  "}', LEN_MSG),
        (json.dumps({"question": "x" * 501}).encode(), LEN_MSG),
        (b'{"question": "hello\\u0000"}', CTRL_MSG),
        (b'{"question": "hello\\u007f"}', CTRL_MSG),
        (b'{"question": "hello", "pipeline": "nope"}', PIPE_MSG),
        (b'{"question": "hello", "pipeline": 3}', PIPE_MSG),
    ],
)
def test_validation_errors_exact_and_limiter_untouched(content: bytes, message: str) -> None:
    limiter = CountingLimiter()
    response = make_client(limiter, make_settings()).post("/stub", content=content)
    assert response.status_code == 422
    assert response.json() == {"error": message}
    assert limiter.calls == 0


def test_valid_request_strips_and_allows_whitespace_controls() -> None:
    limiter = CountingLimiter()
    client = make_client(limiter, make_settings())
    r = client.post("/stub", json={"question": "  abc  "})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "question": "abc", "pipeline": "self_rag"}
    r = client.post("/stub", json={"question": "a\nb\tc", "pipeline": "baseline"})
    assert r.status_code == 200 and r.json()["pipeline"] == "baseline"
    assert limiter.calls == 2


def test_body_too_large_413_before_parsing() -> None:
    limiter = CountingLimiter()
    client = make_client(limiter, make_settings(max_body_bytes=50))
    r = client.post("/stub", content=b"{" + b" " * 100)
    assert r.status_code == 413
    assert r.json() == {"error": "Request body too large."}
    assert limiter.calls == 0


def test_rate_limit_responses() -> None:
    cases = [
        (
            LimitResult(False, 42, "ip"),
            429,
            {"error": "Rate limit reached. Try again later.", "retry_after_s": 42},
        ),
        (
            LimitResult(False, 9, "global"),
            503,
            {"error": "The demo's daily budget is used up. It resets at 00:00 UTC."},
        ),
        (
            LimitResult(False, 0, "unavailable"),
            503,
            {"error": "The service is temporarily unavailable."},
        ),
    ]
    for result, status, body in cases:
        client = make_client(CountingLimiter(result), make_settings())
        r = client.post("/stub", json={"question": "hello"})
        assert r.status_code == status and r.json() == body
        assert r.headers.get("Retry-After") == ("42" if status == 429 else None)


def test_general_handler_hides_traceback(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        r = make_client(CountingLimiter(), make_settings()).get("/boom")
    assert r.status_code == 500
    assert r.json() == {"error": "Internal error."}
    assert "secret-detail" not in r.text and "Traceback" not in r.text
    assert any("ValueError" in rec.getMessage() for rec in caplog.records)


def test_dependency_builds_process_wide_limiter() -> None:
    ratelimit.reset_rate_limiter_state()
    assert rate_limiter_dependency() is rate_limiter_dependency()
    ratelimit.reset_rate_limiter_state()


# ---- pipelines endpoint ----


def test_pipelines_endpoint_matches_registry() -> None:
    body = TestClient(app).get("/api/pipelines").json()
    assert [p["name"] for p in body["pipelines"]] == list_pipelines()
    assert [p["label"] for p in body["pipelines"]] == ["Baseline RAG", "Corrective RAG", "Self-RAG"]
    assert body["pipelines"][0]["description"] == (
        "Retrieves documentation excerpts with hybrid search and answers from them in one LLM call."
    )
    assert body["pipelines"][1]["description"] == (
        "Grades the retrieved excerpts, rewrites the query once if none are relevant, "
        "then falls back to a web search of the docs site."
    )
    assert body["pipelines"][2]["description"] == (
        "Decides whether retrieval is needed, runs the corrective steps, then checks the answer "
        "against the excerpts and regenerates or abstains if it is unsupported."
    )


# ---- sse probe ----


def load_probe() -> Any:
    path = Path(__file__).resolve().parent.parent / "tools" / "sse_probe.py"
    spec = importlib.util.spec_from_file_location("sse_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_parser_split_chunks_comments_and_tail() -> None:
    probe = load_probe()
    text = ': ping\n\nevent: trace\ndata: {"a":1}\n\nevent: answer\ndata: {"b":2}'
    for size in (1, 3, 7, len(text)):
        chunks = [text[i : i + size] for i in range(0, len(text), size)]
        assert list(probe.parse_frames(chunks)) == [
            ("ping", "ping"),
            ("trace", '{"a":1}'),
            ("answer", '{"b":2}'),
        ]


def test_probe_does_not_import_ragdocs() -> None:
    path = Path(__file__).resolve().parent.parent / "tools" / "sse_probe.py"
    source = path.read_text(encoding="utf-8")
    assert "import ragdocs" not in source and "from ragdocs" not in source


# ---- import boundary ----


def test_api_app_import_boundary() -> None:
    script = "import json, sys\nimport ragdocs.api.app\nprint(json.dumps(sorted(sys.modules)))\n"
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    modules = json.loads(out.stdout)
    for forbidden in ("ragdocs.eval", "ragdocs.ingest", "ragdocs.api.local"):
        assert not any(m.startswith(forbidden) for m in modules), forbidden
