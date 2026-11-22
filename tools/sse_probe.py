"""Probe POST /api/ask and print each Server-Sent Events frame with its arrival time.

Purpose: check that the streaming API sends events incrementally (not buffered) and ends
with an "answer" or "error" event.
Inputs: --question (required), --base-url (default http://127.0.0.1:8000), --pipeline
(default self_rag), --timeout seconds (default 70).
Output: one line per frame (elapsed seconds, event name or "ping", data cut to 160
characters), then time to first event, total time, trace event count and final event.
Exit code: 0 if the last event is "answer", 1 for a non-200 response, 2 if it is "error",
3 if the stream ended with neither.
Usage: .venv/Scripts/python tools/sse_probe.py --question "What is a checkpointer?"
Imports only the standard library and httpx; never imports ragdocs.
"""

import argparse
import sys
import time
from collections.abc import Iterable, Iterator

import httpx

DATA_PREVIEW_CHARS = 160


def parse_frames(chunks: Iterable[str]) -> Iterator[tuple[str, str]]:
    """Yield (event name, data) per SSE frame from text chunks split anywhere.

    A comment-only frame yields ("ping", comment text). A final frame without a trailing
    blank line is still yielded when the chunks end.
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


def _print_frame(start: float, name: str, data: str) -> None:
    shown = data if len(data) <= DATA_PREVIEW_CHARS else data[:DATA_PREVIEW_CHARS]
    print(f"{time.monotonic() - start:6.1f}s  {name:<10} {shown}")


def run(base_url: str, pipeline: str, question: str, timeout: float) -> int:
    """Send the request, print frames and a summary; return the exit code."""
    start = time.monotonic()
    first: float | None = None
    last = ""
    traces = 0
    body = {"question": question, "pipeline": pipeline}
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", f"{base_url.rstrip('/')}/api/ask", json=body) as response:
            if response.status_code != 200:
                response.read()
                print(f"status {response.status_code}")
                if "retry-after" in response.headers:
                    print(f"Retry-After: {response.headers['retry-after']}")
                print(response.text)
                return 1
            for name, data in parse_frames(response.iter_text()):
                _print_frame(start, name, data)
                if name == "ping":
                    continue
                first = first if first is not None else time.monotonic() - start
                traces += name == "trace"
                last = name
    total = time.monotonic() - start
    first_text = "none" if first is None else f"{first:.1f}s"
    final = last or "none"
    print(f"first event {first_text}, total {total:.1f}s, trace events {traces}, last {final}")
    return {"answer": 0, "error": 2}.get(last, 3)


def main() -> int:
    """Parse arguments and run the probe."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--pipeline", default="self_rag")
    parser.add_argument("--question", required=True)
    parser.add_argument("--timeout", type=float, default=70)
    args = parser.parse_args()
    return run(args.base_url, args.pipeline, args.question, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
