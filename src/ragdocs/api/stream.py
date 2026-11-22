"""Stream a pipeline's trace and answer as server-sent events (POST /api/ask body).

Runtime-safe module: imports only the standard library, ragdocs.api.sse, ragdocs.config,
ragdocs.schemas, ragdocs.pipelines.base and ragdocs.tracing.

The pipeline runs in a daemon worker thread because its LLM calls block. The async
generator StreamRunner.events() reads the worker's items from an asyncio.Queue, so pings
and the request timeout keep working while a call blocks. Starlette cancels the task that
iterates events() when the client disconnects (verified in M12 S2 Step 0), which runs the
finally block and sets the worker's cancel flag.

Privacy (D10, D18): the single request log line never contains the question, the answer,
a client IP or a key.
"""

import asyncio
import contextvars
import logging
import sys
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

from ragdocs.api.sse import format_event, ping
from ragdocs.config import Settings
from ragdocs.pipelines.base import Pipeline
from ragdocs.schemas import PipelineResult, TraceEvent
from ragdocs.tracing import flush_traces

logger = logging.getLogger("ragdocs.api")

Outcome = Literal["answer", "abstained", "error", "timeout", "disconnected", "limited", "invalid"]

MSG_TIMEOUT = "The request took too long."
MSG_INTERNAL = "Internal error."
MSG_CONFIG = "The server is missing configuration."
# Prefix of the RuntimeError Settings.require raises for an unset key.
MISSING_KEY_PREFIX = "Missing required environment variable"
# Smallest queue wait, so a wait that is already due does not become a busy loop.
MIN_WAIT_S = 0.01
NO_VALUE = "-"

Poll = Callable[[asyncio.Queue[Any], float], Awaitable[Any]]


def configure_request_logging() -> None:
    """Send the "ragdocs.api" loggers to stderr at INFO, once per process.

    Neither uvicorn nor the Vercel runtime configures the root logger, so without this
    the request log line would be dropped. Records still propagate to the root logger.
    """
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


async def default_poll(queue: asyncio.Queue[Any], timeout: float) -> Any:
    """Return the next queue item or raise asyncio.TimeoutError after timeout seconds."""
    return await asyncio.wait_for(queue.get(), timeout)


async def never_disconnected() -> bool:
    """Default is_disconnected: the client is assumed to be connected."""
    return False


def log_request(
    pipeline: str,
    outcome: Outcome,
    latency_ms: int,
    question_chars: int | None,
    result: PipelineResult | None = None,
    limit_reason: str | None = None,
) -> None:
    """Write the one INFO line for an /api/ask request (key=value pairs, no visitor data)."""
    calls = str(result.llm_calls) if result else NO_VALUE
    web = str(result.used_web).lower() if result else NO_VALUE
    chars = NO_VALUE if question_chars is None else str(question_chars)
    line = (
        f"pipeline={pipeline} outcome={outcome} latency_ms={latency_ms} "
        f"llm_calls={calls} used_web={web} question_chars={chars}"
    )
    if limit_reason:
        line += f" limit_reason={limit_reason}"
    logger.info(line)


class StreamRunner:
    """Run one pipeline for one question and yield ready-to-send SSE frames."""

    def __init__(
        self,
        pipeline_name: str,
        question: str,
        settings: Settings,
        load_pipeline: Callable[[str], Pipeline],
        tracing_active: bool,
        clock: Callable[[], float] = time.monotonic,
        poll: Poll = default_poll,
        is_disconnected: Callable[[], Awaitable[bool]] = never_disconnected,
        flush: Callable[[], None] = flush_traces,
        started_at: float | None = None,
    ) -> None:
        self._name = pipeline_name
        self._question = question
        self._settings = settings
        self._load = load_pipeline
        self._tracing = tracing_active
        self._clock = clock
        self._poll = poll
        self._is_disconnected = is_disconnected
        self._flush = flush
        self._started_at = started_at
        self._cancel = threading.Event()
        self._outcome: Outcome | None = None
        self._result: PipelineResult | None = None
        self._flush_pending = False

    @property
    def cancel_flag(self) -> threading.Event:
        """Set when the worker thread must stop at its next event."""
        return self._cancel

    # ---- worker thread ----

    def _work(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[Any]) -> None:
        """Load and iterate the pipeline, handing every item to the event loop."""

        def put(item: tuple[Any, ...]) -> bool:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, item)
            except RuntimeError:  # the loop is closed
                return False
            return True

        stream: Any = None
        try:
            pipeline = self._load(self._name)
            meta = {"source": "api", "pipeline": self._name} if self._tracing else None
            stream = pipeline.stream(self._question, run_metadata=meta)
            for event in stream:
                if self._cancel.is_set() or not put(("event", event)):
                    break
        except Exception as exc:
            missing = isinstance(exc, RuntimeError) and str(exc).startswith(MISSING_KEY_PREFIX)
            put(("exception", type(exc).__name__, missing))
        finally:
            self._close_stream(stream)
            put(("done", None))

    @staticmethod
    def _close_stream(stream: Any) -> None:
        close = getattr(stream, "close", None)
        if close is None:
            return
        try:
            close()
        except Exception as exc:
            logger.warning("closing the pipeline stream raised %s", type(exc).__name__)

    # ---- event loop side ----

    def _handle(self, item: tuple[Any, ...]) -> tuple[list[str], bool]:
        """Return (frames to send, stop) for one queue item; sets the outcome when stopping."""
        kind = item[0]
        if kind == "event":
            return self._handle_event(item[1])
        if kind == "exception":
            logger.error("Request failed: %s", item[1])
            message = MSG_CONFIG if item[2] else MSG_INTERNAL
            return self._error(message)
        return self._error(MSG_INTERNAL)  # "done" before any answer or error

    def _handle_event(self, event: TraceEvent) -> tuple[list[str], bool]:
        if event.type == "answer":
            return self._handle_answer(event)
        if event.type == "error":
            return self._error(event.message)
        return [format_event("trace", event.model_dump(mode="json"))], False

    def _handle_answer(self, event: TraceEvent) -> tuple[list[str], bool]:
        try:
            result = PipelineResult.model_validate(event.data)
        except ValueError as exc:
            logger.error("Request failed: %s", type(exc).__name__)
            return self._error(MSG_INTERNAL)
        self._result = result
        self._outcome = "abstained" if result.answer.abstained else "answer"
        self._flush_pending = self._tracing
        return [format_event("answer", result.model_dump(mode="json"))], True

    def _error(self, message: str) -> tuple[list[str], bool]:
        self._outcome = "error"
        return [format_event("error", {"error": message})], True

    async def _flush_bounded(self) -> None:
        """Flush traces in a daemon thread; give up after trace_flush_timeout_s."""

        def target() -> None:
            try:
                self._flush()
            except Exception as exc:
                logger.warning("trace flush failed: %s", type(exc).__name__)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        await asyncio.to_thread(thread.join, self._settings.trace_flush_timeout_s)
        if thread.is_alive():
            logger.warning("trace flush timed out")

    async def events(self) -> AsyncIterator[str]:
        """Yield SSE frames until the answer, an error, the timeout or a disconnect."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        start = last_sent = self._clock()
        request_start = start if self._started_at is None else self._started_at
        try:
            # copy_context: LangChain callbacks and tracing live in ContextVars, which a new
            # thread would not inherit (M12 S2 Step 6: the budget recorder saw no Groq calls).
            context = contextvars.copy_context()
            worker = threading.Thread(
                target=context.run, args=(self._work, loop, queue), daemon=True
            )
            worker.start()
            while True:
                if await self._is_disconnected():
                    self._outcome = "disconnected"
                    return
                elapsed = self._clock() - start
                if elapsed >= self._settings.request_timeout_s:
                    self._outcome = "timeout"
                    yield format_event("error", {"error": MSG_TIMEOUT})
                    return
                wait = min(
                    self._settings.sse_ping_interval_s - (self._clock() - last_sent),
                    self._settings.request_timeout_s - elapsed,
                )
                try:
                    item = await self._poll(queue, max(wait, MIN_WAIT_S))
                except TimeoutError:
                    if self._clock() - last_sent >= self._settings.sse_ping_interval_s:
                        yield ping()
                        last_sent = self._clock()
                    continue
                frames, stop = self._handle(item)
                for frame in frames:
                    yield frame
                last_sent = self._clock()
                if stop:
                    # Resumes only after the answer frame was sent.
                    if self._flush_pending:
                        await self._flush_bounded()
                    return
        finally:
            self._cancel.set()
            if self._outcome is None:  # cancelled or closed mid-await
                self._outcome = "disconnected"
            latency_ms = int((self._clock() - request_start) * 1000)
            log_request(self._name, self._outcome, latency_ms, len(self._question), self._result)
