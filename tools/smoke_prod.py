"""Smoke test for a deployed (or local) LangGraph Docs Assistant.

Purpose: after a deploy, check the static page, the security and cache headers, the JSON
endpoints and one streamed answer per pipeline, and print one pass/fail row per check.
Inputs: --base-url URL (required); --local (expect env "local", skip the Vercel-only header
checks 2 to 4); --pipelines a,b,c (default baseline,corrective,self_rag; at most 3, each
asked once); --no-asks (skip check 9); --question TEXT (default DEFAULT_QUESTION);
--max-seconds N (default 45, limit for one streamed answer).
Output: a table "check | result | detail" on stdout. Check 9 sends at most 3 valid
POST /api/ask requests per run (15 s apart); check 8 sends an invalid one that uses no quota.
Exit code: 0 if no check failed, 1 otherwise.
Usage: .venv/Scripts/python tools/smoke_prod.py --base-url https://example.vercel.app
       py tasks.py smoke --url http://127.0.0.1:8000 --local --pipelines baseline
Imports only the standard library and httpx; never imports ragdocs.
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

import httpx

# The q001 question of data/eval/eval_set.jsonl, copied exactly.
DEFAULT_QUESTION = (
    "My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?"
)

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)
PAGE_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cache-control": "no-cache",
}
ASSET_CACHE = "public, max-age=31536000, immutable"
RESULTS_CACHE = "public, max-age=300"
TITLE = "<title>LangGraph Docs Assistant</title>"
PIPELINE_NAMES = ["baseline", "corrective", "self_rag"]
INVALID_QUESTION_ERROR = "The question must be between 3 and 500 characters."
MAX_ASKS = 3
ASK_GAP_S = 15.0
MIN_STREAM_SPREAD_S = 0.3
DEFAULT_MAX_SECONDS = 45.0
REQUEST_TIMEOUT_MARGIN_S = 15.0
ASSET_RE = re.compile(r'(?:src|href)="(/assets/[^"]+\.(js|css))"')

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


@dataclass
class Row:
    """One line of the result table."""

    name: str
    status: str
    detail: str = ""


def parse_frames(chunks: Iterable[str]) -> Iterator[tuple[str, str]]:
    """Yield (event name, data) per SSE frame from text chunks split anywhere.

    A comment-only frame yields ("ping", comment text). A final frame without a trailing
    blank line is still yielded when the chunks end. Copied from tools/sse_probe.py.
    """
    buffer = ""
    for chunk in chunks:
        buffer += chunk.replace("\r\n", "\n")
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            parsed = _parse_frame(frame)
            if parsed:
                yield parsed
    parsed = _parse_frame(buffer)
    if parsed:
        yield parsed


def _parse_frame(frame: str) -> tuple[str, str] | None:
    """Parse one frame's lines; None for an empty frame."""
    name, data, comment = "message", [], []
    for line in frame.split("\n"):
        if line.startswith(":"):
            comment.append(line[1:].strip())
        elif line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data or name != "message":
        return name, "\n".join(data)
    if comment:
        return "ping", " ".join(comment)
    return None


def _row(name: str, problems: list[str], detail: str = "") -> Row:
    return Row(name, FAIL if problems else PASS, "; ".join(problems) or detail)


def _get(client: httpx.Client, path: str) -> httpx.Response | str:
    """GET path; return the response or an error text."""
    try:
        return client.get(path)
    except httpx.HTTPError as exc:
        return f"request failed: {type(exc).__name__}"


def check_index(client: httpx.Client) -> tuple[Row, str]:
    """Check 1: GET / is the page with the CSP. Returns the row and the HTML."""
    name = "1 GET / page and CSP"
    resp = _get(client, "/")
    if isinstance(resp, str):
        return Row(name, FAIL, resp), ""
    problems = []
    if resp.status_code != 200:
        problems.append(f"status {resp.status_code}")
    if not resp.headers.get("content-type", "").startswith("text/html"):
        problems.append(f"content-type {resp.headers.get('content-type')!r}")
    if TITLE not in resp.text:
        problems.append("title missing")
    if resp.headers.get("content-security-policy") != CSP:
        problems.append("Content-Security-Policy differs")
    return _row(name, problems, "200 text/html, title, CSP"), resp.text


def check_page_headers(client: httpx.Client) -> Row:
    """Check 2: security headers and no-cache on GET /."""
    name = "2 GET / security headers"
    resp = _get(client, "/")
    if isinstance(resp, str):
        return Row(name, FAIL, resp)
    problems = [
        f"{key}: {resp.headers.get(key)!r}"
        for key, value in PAGE_HEADERS.items()
        if resp.headers.get(key) != value
    ]
    return _row(name, problems, "4 headers match")


def check_assets(client: httpx.Client, html: str) -> Row:
    """Check 3: the first referenced JS and CSS files are cached as immutable."""
    name = "3 /assets cache headers"
    found = ASSET_RE.findall(html)
    paths = [next((p for p, ext in found if ext == e), None) for e in ("js", "css")]
    if None in paths:
        return Row(name, FAIL, "index.html references no /assets js or css (or / failed)")
    problems = []
    for path in paths:
        resp = _get(client, str(path))
        if isinstance(resp, str):
            problems.append(f"{path}: {resp}")
        elif resp.status_code != 200:
            problems.append(f"{path}: status {resp.status_code}")
        elif resp.headers.get("cache-control") != ASSET_CACHE:
            problems.append(f"{path}: cache-control {resp.headers.get('cache-control')!r}")
    return _row(name, problems, " and ".join(str(p) for p in paths))


def check_results(client: httpx.Client) -> Row:
    """Check 4: /results.json is JSON with 3 pipelines and a 5-minute cache."""
    name = "4 /results.json"
    resp = _get(client, "/results.json")
    if isinstance(resp, str):
        return Row(name, FAIL, resp)
    problems = []
    if resp.status_code != 200:
        problems.append(f"status {resp.status_code}")
    else:
        try:
            count = len(resp.json()["pipelines"])
        except (ValueError, KeyError, TypeError):
            count = -1
        if count != 3:
            problems.append(f"pipelines: {count}")
    if resp.headers.get("cache-control") != RESULTS_CACHE:
        problems.append(f"cache-control {resp.headers.get('cache-control')!r}")
    return _row(name, problems, "3 pipelines, cache 300 s")


def check_health(client: httpx.Client, expected_env: str) -> Row:
    """Check 5: /api/health reports status ok and the expected env."""
    name = "5 /api/health"
    resp = _get(client, "/api/health")
    if isinstance(resp, str):
        return Row(name, FAIL, resp)
    try:
        data = resp.json()
    except ValueError:
        data = {}
    problems = []
    if resp.status_code != 200:
        problems.append(f"status {resp.status_code}")
    if data.get("status") != "ok":
        problems.append(f"status field {data.get('status')!r}")
    if data.get("env") != expected_env:
        problems.append(f"env {data.get('env')!r}, expected {expected_env!r}")
    return _row(name, problems, f"ok, env {expected_env}, commit {data.get('commit')}")


def check_pipelines(client: httpx.Client) -> Row:
    """Check 6: /api/pipelines lists exactly the three names in order."""
    name = "6 /api/pipelines"
    resp = _get(client, "/api/pipelines")
    if isinstance(resp, str):
        return Row(name, FAIL, resp)
    try:
        names = [p["name"] for p in resp.json()["pipelines"]]
    except (ValueError, KeyError, TypeError):
        names = []
    problems = [] if resp.status_code == 200 else [f"status {resp.status_code}"]
    if names != PIPELINE_NAMES:
        problems.append(f"names {names}")
    return _row(name, problems, ", ".join(PIPELINE_NAMES))


def check_probe_gone(client: httpx.Client) -> Row:
    """Check 7: the removed /api/deps-probe route answers 404."""
    name = "7 /api/deps-probe is gone"
    resp = _get(client, "/api/deps-probe")
    if isinstance(resp, str):
        return Row(name, FAIL, resp)
    return _row(name, [] if resp.status_code == 404 else [f"status {resp.status_code}"], "404")


def check_validation(client: httpx.Client) -> Row:
    """Check 8: a 2-character question gets the exact 422 body (no quota used)."""
    name = "8 POST /api/ask validation"
    try:
        resp = client.post("/api/ask", json={"question": "hi", "pipeline": "baseline"})
    except httpx.HTTPError as exc:
        return Row(name, FAIL, f"request failed: {type(exc).__name__}")
    try:
        body = resp.json()
    except ValueError:
        body = None
    ok = resp.status_code == 422 and body == {"error": INVALID_QUESTION_ERROR}
    return _row(name, [] if ok else [f"status {resp.status_code}, body {resp.text[:120]!r}"], "422")


def ask_once(
    client: httpx.Client,
    pipeline: str,
    question: str,
    max_seconds: float,
    clock: Callable[[], float],
) -> Row:
    """Check 9 for one pipeline: stream one answer and verify it arrived progressively."""
    name = f"9 ask {pipeline}"
    start = clock()
    events: list[tuple[str, float, str]] = []
    try:
        with client.stream(
            "POST", "/api/ask", json={"question": question, "pipeline": pipeline}
        ) as resp:
            if resp.status_code != 200:
                resp.read()
                return Row(name, FAIL, f"status {resp.status_code}: {resp.text[:200]}")
            if not resp.headers.get("content-type", "").startswith("text/event-stream"):
                return Row(name, FAIL, f"content-type {resp.headers.get('content-type')!r}")
            for event, data in parse_frames(resp.iter_text()):
                if event != "ping":
                    events.append((event, clock() - start, data))
    except httpx.HTTPError as exc:
        return Row(name, FAIL, f"request failed: {type(exc).__name__}")
    return _judge_stream(name, events, max_seconds)


def _judge_stream(name: str, events: list[tuple[str, float, str]], max_seconds: float) -> Row:
    """Apply the stream rules of check 9 to the (event, seconds, data) list."""
    if not events:
        return Row(name, FAIL, "no events")
    first, total = events[0][1], events[-1][1]
    last_name, _, last_data = events[-1]
    problems = []
    if last_name != "answer":
        problems.append(f"last event {last_name!r}: {last_data[:120]}")
    if not any(e[0] == "trace" for e in events[:-1]):
        problems.append("no trace event before the answer")
    if last_name == "answer" and not _answer_text(last_data):
        problems.append("empty answer text")
    if total > max_seconds:
        problems.append(f"total {total:.1f}s over {max_seconds:g}s")
    if total - first < MIN_STREAM_SPREAD_S:
        problems.append("events arrived together; possible buffering")
    return _row(
        name, problems, f"first event {first:.1f}s, total {total:.1f}s, {len(events)} events"
    )


def _answer_text(data: str) -> str:
    try:
        return str(json.loads(data)["answer"]["text"]).strip()
    except (ValueError, KeyError, TypeError):
        return ""


def run_checks(
    client: httpx.Client,
    *,
    local: bool,
    pipelines: list[str],
    asks: bool,
    question: str,
    max_seconds: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Row]:
    """Run every check against client (base_url already set) and return the rows."""
    index_row, html = check_index(client)
    rows = [index_row]
    if local:
        rows += [
            Row(n, SKIP, "--local")
            for n in ("2 GET / security headers", "3 /assets cache headers", "4 /results.json")
        ]
    else:
        rows += [check_page_headers(client), check_assets(client, html), check_results(client)]
    rows += [
        check_health(client, "local" if local else "production"),
        check_pipelines(client),
        check_probe_gone(client),
        check_validation(client),
    ]
    if not asks:
        return rows + [Row("9 ask", SKIP, "--no-asks")]
    for i, pipeline in enumerate(pipelines):
        if i:
            sleep(ASK_GAP_S)
        rows.append(ask_once(client, pipeline, question, max_seconds, clock))
    return rows


def format_table(rows: list[Row]) -> str:
    """Return the rows as an aligned text table."""
    width = max(len(r.name) for r in rows)
    lines = [f"{'check'.ljust(width)}  result  detail"]
    lines += [f"{r.name.ljust(width)}  {r.status:<6}  {r.detail}" for r in rows]
    return "\n".join(lines)


def parse_pipelines(value: str) -> list[str]:
    """Split a comma list; reject unknown names, duplicates and more than MAX_ASKS entries."""
    names = [n.strip() for n in value.split(",") if n.strip()]
    if not names or len(names) > MAX_ASKS or len(set(names)) != len(names):
        raise argparse.ArgumentTypeError(f"give 1 to {MAX_ASKS} distinct pipeline names")
    unknown = [n for n in names if n not in PIPELINE_NAMES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown pipeline(s): {', '.join(unknown)}")
    return names


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the checks, print the table; return the exit code."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--pipelines", type=parse_pipelines, default=list(PIPELINE_NAMES))
    parser.add_argument("--no-asks", action="store_true")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    args = parser.parse_args(argv)
    timeout = args.max_seconds + REQUEST_TIMEOUT_MARGIN_S
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=timeout) as client:
        rows = run_checks(
            client,
            local=args.local,
            pipelines=args.pipelines,
            asks=not args.no_asks,
            question=args.question,
            max_seconds=args.max_seconds,
        )
    print(format_table(rows))
    return 1 if any(r.status == FAIL for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
