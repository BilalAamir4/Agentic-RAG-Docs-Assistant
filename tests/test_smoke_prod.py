"""Tests for tools/smoke_prod.py (no network: httpx.MockTransport)."""

import importlib.util
import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load("smoke_prod")
probe = _load("sse_probe")

PAGE = (
    "<html><head><title>LangGraph Docs Assistant</title>"
    '<script src="/assets/index-AAA.js"></script><link href="/assets/index-BBB.css"></head></html>'
)
ANSWER = json.dumps(
    {"answer": {"text": "Use recursion_limit.", "citations": [], "abstained": False}}
)
SSE = (
    'event: trace\ndata: {"type":"node_start"}\n\n: ping\n\n'
    'event: trace\ndata: {"type":"node_end"}\n\n'
    f"event: answer\ndata: {ANSWER}\n\n"
)


def make_handler(
    env: str = "production", overrides: dict | None = None, asks: list | None = None
) -> Callable[[httpx.Request], httpx.Response]:
    """Return a handler for a server that passes every check; overrides[key] replaces a response."""
    overrides = overrides or {}

    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url.path}"
        if key in overrides:
            return overrides[key]
        sec = {
            "content-security-policy": smoke.CSP,
            "x-content-type-options": "nosniff",
            "referrer-policy": "strict-origin-when-cross-origin",
            "permissions-policy": "camera=(), microphone=(), geolocation=()",
        }
        if key == "GET /":
            return httpx.Response(
                200,
                text=PAGE,
                headers={"content-type": "text/html", "cache-control": "no-cache", **sec},
            )
        if key.startswith("GET /assets/"):
            return httpx.Response(200, text="x", headers={"cache-control": smoke.ASSET_CACHE})
        if key == "GET /results.json":
            return httpx.Response(
                200, json={"pipelines": [1, 2, 3]}, headers={"cache-control": smoke.RESULTS_CACHE}
            )
        if key == "GET /api/health":
            return httpx.Response(200, json={"status": "ok", "env": env, "commit": "abc1234"})
        if key == "GET /api/pipelines":
            return httpx.Response(
                200, json={"pipelines": [{"name": n} for n in smoke.PIPELINE_NAMES]}
            )
        if key == "POST /api/ask":
            body = json.loads(request.content)
            if len(body["question"]) < 3:
                return httpx.Response(422, json={"error": smoke.INVALID_QUESTION_ERROR})
            if asks is not None:
                asks.append(body["pipeline"])
            return httpx.Response(
                200, text=SSE, headers={"content-type": "text/event-stream; charset=utf-8"}
            )
        return httpx.Response(404, json={"detail": "Not Found"})

    return handler


def make_clock(step: float = 0.5) -> Callable[[], float]:
    """A fake clock that advances by step at every call."""
    state = {"t": 0.0}

    def clock() -> float:
        state["t"] += step
        return state["t"]

    return clock


def run(handler: Callable[[httpx.Request], httpx.Response], **kw: object) -> dict[str, object]:
    """Run all checks against the handler; return {check name: Row}."""
    params: dict = {
        "local": False,
        "pipelines": ["baseline"],
        "asks": True,
        "question": smoke.DEFAULT_QUESTION,
        "max_seconds": 45.0,
        "clock": make_clock(),
        "sleep": lambda _s: None,
    }
    params.update(kw)
    with httpx.Client(base_url="http://t", transport=httpx.MockTransport(handler)) as client:
        rows = smoke.run_checks(client, **params)
    return {
        r.name.split(" ")[0] + (" " + r.name.split(" ")[-1] if r.name.startswith("9") else ""): r
        for r in rows
    }


def test_all_pass() -> None:
    """A fully passing fake server gives no FAIL and no SKIP."""
    rows = run(make_handler(), pipelines=smoke.PIPELINE_NAMES)
    assert [r.status for r in rows.values()] == ["PASS"] * 11, smoke.format_table(
        list(rows.values())
    )


FAILURES = {
    "1": (
        "GET /",
        httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"}),
    ),
    "2": (
        "GET /",
        httpx.Response(
            200,
            text=PAGE,
            headers={"content-type": "text/html", "content-security-policy": smoke.CSP},
        ),
    ),
    "3": ("GET /assets/index-AAA.js", httpx.Response(200, text="x")),
    "4": ("GET /results.json", httpx.Response(200, json={"pipelines": []})),
    "5": ("GET /api/health", httpx.Response(200, json={"status": "ok", "env": "local"})),
    "6": ("GET /api/pipelines", httpx.Response(200, json={"pipelines": [{"name": "baseline"}]})),
    "7": ("GET /api/deps-probe", httpx.Response(200, json={})),
    "8": ("POST /api/ask", httpx.Response(200, text="")),
}


@pytest.mark.parametrize("check", sorted(FAILURES))
def test_each_check_fails_on_its_own(check: str) -> None:
    """Breaking one response fails that check; checks 3 and 7 and 8 fail only themselves."""
    key, response = FAILURES[check]
    handler = make_handler(overrides={key: response})
    if check == "7":
        # the default handler already answers 404 for unknown paths; force a 200 instead
        inner = handler

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/deps-probe":
                return response
            return inner(request)

    rows = run(handler, asks=False)
    assert rows[check].status == "FAIL"


@pytest.mark.parametrize(
    ("label", "response", "message"),
    [
        ("429", httpx.Response(429, json={"error": "Rate limit reached."}), "status 429"),
        ("503", httpx.Response(503, json={"error": "budget"}), "status 503"),
        (
            "empty",
            httpx.Response(
                200,
                text='event: trace\ndata: {}\n\nevent: answer\ndata: {"answer":{"text":" "}}\n\n',
                headers={"content-type": "text/event-stream"},
            ),
            "empty answer text",
        ),
        (
            "no trace",
            httpx.Response(
                200,
                text=f"event: answer\ndata: {ANSWER}\n\n",
                headers={"content-type": "text/event-stream"},
            ),
            "no trace event",
        ),
        (
            "error last",
            httpx.Response(
                200,
                text='event: trace\ndata: {}\n\nevent: error\ndata: {"error":"x"}\n\n',
                headers={"content-type": "text/event-stream"},
            ),
            "last event 'error'",
        ),
        (
            "not sse",
            httpx.Response(200, text="x", headers={"content-type": "text/plain"}),
            "content-type",
        ),
    ],
)
def test_ask_failures(label: str, response: httpx.Response, message: str) -> None:
    """Check 9 fails for each bad stream and shows the status and body of 429 and 503."""
    rows = run(
        make_handler(overrides={"POST /api/ask": response}) if False else _ask_handler(response)
    )
    row = rows["9 baseline"]
    assert row.status == "FAIL", label
    assert message in row.detail


def _ask_handler(response: httpx.Response) -> Callable[[httpx.Request], httpx.Response]:
    base = make_handler()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/ask" and len(json.loads(request.content)["question"]) >= 3:
            return response
        return base(request)

    return handler


def test_429_body_is_shown() -> None:
    """A 429 failure carries the response body."""
    rows = run(_ask_handler(httpx.Response(429, json={"error": "Rate limit reached."})))
    assert "Rate limit reached." in rows["9 baseline"].detail


def test_buffering_detected() -> None:
    """Frames that arrive at the same time fail with the buffering message."""
    rows = run(make_handler(), clock=lambda: 1.0)
    assert rows["9 baseline"].status == "FAIL"
    assert "events arrived together; possible buffering" in rows["9 baseline"].detail


def test_too_slow() -> None:
    """A total above --max-seconds fails."""
    rows = run(make_handler(), max_seconds=0.6)
    assert "over 0.6s" in rows["9 baseline"].detail


def test_local_skips_header_checks_and_expects_local_env() -> None:
    """--local skips checks 2 to 4 and accepts env 'local' only."""
    rows = run(make_handler(env="local"), local=True, asks=False)
    assert [rows[k].status for k in ("2", "3", "4")] == ["SKIP"] * 3
    assert rows["5"].status == "PASS"
    assert run(make_handler(env="production"), local=True, asks=False)["5"].status == "FAIL"
    assert run(make_handler(env="local"), local=False, asks=False)["5"].status == "FAIL"


def test_no_asks_sends_no_valid_ask() -> None:
    """--no-asks sends only the invalid question of check 8."""
    asks: list[str] = []
    run(make_handler(asks=asks), asks=False)
    assert asks == []


def test_one_valid_ask_per_pipeline_with_gaps() -> None:
    """Each pipeline is asked once, in order, with the 15 s gap between asks."""
    asks: list[str] = []
    sleeps: list[float] = []
    run(make_handler(asks=asks), pipelines=smoke.PIPELINE_NAMES, sleep=sleeps.append)
    assert asks == smoke.PIPELINE_NAMES
    assert sleeps == [15.0, 15.0]


def test_pipelines_argument_limits() -> None:
    """More than 3, duplicates and unknown names are rejected."""
    import argparse

    for bad in ("baseline,baseline", "a", "baseline,corrective,self_rag,baseline", ""):
        with pytest.raises(argparse.ArgumentTypeError):
            smoke.parse_pipelines(bad)
    assert smoke.parse_pipelines("self_rag,baseline") == ["self_rag", "baseline"]


def test_default_question_is_q001() -> None:
    """DEFAULT_QUESTION equals the q001 question of the eval set."""
    for line in (
        (ROOT / "data" / "eval" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        item = json.loads(line)
        if item["id"] == "q001":
            assert smoke.DEFAULT_QUESTION == item["question"]
            return
    pytest.fail("q001 not found")


def _split_every_byte(text: str) -> Iterator[str]:
    raw = text.encode("utf-8")
    for i in range(len(raw)):
        yield raw[i : i + 1].decode("utf-8", errors="ignore")


def test_parser_matches_sse_probe() -> None:
    """The copied parser yields the same frames as tools/sse_probe.py on a stream split per byte."""
    sample = SSE + "event: trace\ndata: né\n\n"
    ascii_sample = sample.replace("né", "ne")
    assert list(smoke.parse_frames(_split_every_byte(ascii_sample))) == list(
        probe.parse_frames(_split_every_byte(ascii_sample))
    )
    assert list(smoke.parse_frames([sample])) == list(probe.parse_frames([sample]))
    assert len(list(smoke.parse_frames(_split_every_byte(ascii_sample)))) == 5


def test_tool_does_not_import_ragdocs() -> None:
    """The tool is standalone: no ragdocs import in its source."""
    source = (ROOT / "tools" / "smoke_prod.py").read_text(encoding="utf-8")
    assert "import ragdocs" not in source
    assert "from ragdocs" not in source
