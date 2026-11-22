"""Server-Sent Events formatting helpers for the streaming API."""

import json
from typing import Any

# Cache-Control stops proxies from storing the stream; X-Accel-Buffering tells
# nginx-style proxies not to buffer it. Content-Type is set by the response class.
SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}

SSE_MEDIA_TYPE = "text/event-stream; charset=utf-8"


def format_event(event_name: str, payload: dict[str, Any]) -> str:
    """Return one SSE frame: ``event: <name>`` and a single-line JSON ``data:`` line."""
    if "\n" in event_name or "\r" in event_name:
        raise ValueError("SSE event name must not contain a newline.")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event_name}\ndata: {data}\n\n"


def ping() -> str:
    """Return an SSE comment frame used as a keep-alive."""
    return ": ping\n\n"
