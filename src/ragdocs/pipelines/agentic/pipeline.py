"""AgenticPipeline: streams a compiled agentic graph as TraceEvents (M10).

LangSmith trace shape (D22): parent run named after the mode ("corrective"), the
LangGraph run "graph" inside it, node runs inside that, and "hybrid_retrieve" /
"tavily_search" inside the retrieve and web_search nodes.

Runtime-safe: never imports ragdocs.eval or ragdocs.ingest.
"""

import time
from collections.abc import Iterator
from typing import Any

from ragdocs.pipelines.agentic.graph import Mode, build_default_deps, build_graph
from ragdocs.pipelines.agentic.state import AgenticDeps, initial_state
from ragdocs.providers.llm import CallCounter
from ragdocs.schemas import PipelineResult, TraceEvent
from ragdocs.tracing import TracedRun, traced_run

# Graph steps allowed per question. Corrective worst case is 7 steps; LangGraph's own
# default is 10007 (M10 S1), so the limit is always passed explicitly.
RECURSION_LIMIT = 20
# State keys the pipeline keeps from node updates (no checkpointer).
TRACKED_KEYS = ("answer", "contexts", "used_web", "diagnostics")


class AgenticPipeline:
    """Corrective (M10) or self-RAG (M11) pipeline over a LangGraph StateGraph."""

    def __init__(self, mode: Mode, deps: AgenticDeps | None = None) -> None:
        """Compile the graph for mode; deps default to build_default_deps() (real clients)."""
        self.name: str = mode
        self.mode: Mode = mode
        self.deps = deps if deps is not None else build_default_deps()
        self.graph = build_graph(mode, self.deps)

    def graph_config(
        self, counter: CallCounter, metadata: dict[str, Any], callbacks: list[Any]
    ) -> dict[str, Any]:
        """RunnableConfig for graph.stream: call counter first, then caller callbacks."""
        return {
            "callbacks": [counter, *callbacks],
            "run_name": "graph",
            "metadata": metadata,
            "recursion_limit": RECURSION_LIMIT,
        }

    def stream(
        self,
        question: str,
        run_metadata: dict[str, Any] | None = None,
        callbacks: list[Any] | None = None,
    ) -> Iterator[TraceEvent]:
        """Run the graph and yield each node's events as they arrive, then the answer.

        t_ms is stamped when each event is yielded. The final event has type 'answer'
        and data=PipelineResult.model_dump(); its trace holds every yielded event in
        yield order with the answer event last, as in BaselinePipeline. On any exception
        (including GraphRecursionError) one 'error' event with the exception class name
        only is yielded and the stream stops.
        """
        metadata = {"pipeline": self.name, **(run_metadata or {})}
        with traced_run(
            name=self.name, run_type="chain", inputs={"question": question}, metadata=metadata
        ) as parent:
            yield from self._stream_events(question, metadata, parent, callbacks or [])

    def _stream_events(
        self, question: str, metadata: dict[str, Any], parent: TracedRun, callbacks: list[Any]
    ) -> Iterator[TraceEvent]:
        """Yield stamped node events, then the answer event (or one error event)."""
        start = time.perf_counter()

        def t_ms() -> int:
            return int((time.perf_counter() - start) * 1000)

        counter = CallCounter()
        config = self.graph_config(counter, metadata, callbacks)
        trace: list[TraceEvent] = []
        latest: dict[str, Any] = {"answer": None, "contexts": [], "used_web": False}
        try:
            for update in self.graph.stream(initial_state(question), config, stream_mode="updates"):
                for node_update in update.values():
                    if not node_update:
                        continue
                    latest.update({k: node_update[k] for k in TRACKED_KEYS if k in node_update})
                    for event in node_update.get("events", []):
                        stamped = event.model_copy(update={"t_ms": t_ms()})
                        trace.append(stamped)
                        yield stamped
            if latest["answer"] is None:
                raise RuntimeError("graph finished without an answer")
            result = PipelineResult(
                question=question,
                pipeline=self.name,
                answer=latest["answer"],
                contexts=latest["contexts"],
                trace=trace,
                llm_calls=counter.llm_calls,
                latency_ms=t_ms(),
                used_web=latest["used_web"],
            )
            # Same construction as BaselinePipeline: the answer event is the last entry of
            # result.trace, and its data is re-dumped so the yielded data holds that trace.
            e_answer = TraceEvent(
                type="answer",
                node="answer",
                message="Pipeline execution finished",
                data=result.model_dump(),
                t_ms=t_ms(),
            )
            trace.append(e_answer)
            result.trace = trace
            e_answer.data = result.model_dump()
            parent.set_outputs(_parent_outputs(result, latest.get("diagnostics", {})))
            yield e_answer
        except Exception as exc:
            message = type(exc).__name__
            parent.set_error(message)
            yield TraceEvent(type="error", node="error", message=message, t_ms=t_ms())


def _parent_outputs(result: PipelineResult, diagnostics: dict[str, Any]) -> dict[str, Any]:
    """Outputs of the parent run: the baseline's fields plus used_web and diagnostics."""
    return {
        "answer": result.answer.text,
        "abstained": result.answer.abstained,
        "n_citations": len(result.answer.citations),
        "llm_calls": result.llm_calls,
        "latency_ms": result.latency_ms,
        "used_web": result.used_web,
        "diagnostics": diagnostics,
    }
