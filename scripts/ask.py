"""CLI tool to query RAG pipelines and stream execution trace events.

Usage:
    .venv\\Scripts\\python scripts\\ask.py --pipeline baseline "question"
"""

import argparse
import sys

from ragdocs.config import get_settings
from ragdocs.pipelines.registry import get_pipeline
from ragdocs.schemas import PipelineResult, TraceEvent
from ragdocs.tracing import configure_tracing, flush_traces, last_trace_url


def format_event_line(event: TraceEvent) -> str:
    """Format a TraceEvent as a single readable status line."""
    details = ""
    if event.type == "retrieval":
        mode = event.data.get("mode", "unknown")
        n_chunks = len(event.data.get("chunks", []))
        details = f" ({n_chunks} chunks, mode={mode})"
    elif event.type == "node_end" and event.node == "generate":
        dropped = event.data.get("dropped_citations", 0)
        uncited = event.data.get("uncited", False)
        details = f" (dropped_citations={dropped}, uncited={uncited})"

    return f"[{event.t_ms:>5}ms] [{event.type:<10}] {event.node}: {event.message}{details}"


def main() -> None:
    """Parse CLI arguments, stream pipeline execution, and print results."""
    # Ensure Windows console handles UTF-8 characters properly at startup
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Query documentation using a specified RAG pipeline."
    )
    parser.add_argument(
        "--pipeline",
        default="baseline",
        help="Pipeline name to execute (default: baseline)",
    )
    parser.add_argument(
        "question",
        help="User question to answer",
    )
    args = parser.parse_args()

    tracing_active = configure_tracing(get_settings())
    try:
        exit_code = _ask(args.pipeline, args.question)
    finally:
        flush_traces()
    if tracing_active:
        url = last_trace_url()
        print(f"\nLangSmith trace: {url}" if url else "\nLangSmith trace: none recorded")
    if exit_code:
        sys.exit(exit_code)


def _ask(pipeline_name: str, question: str) -> int:
    """Stream one pipeline run, print events and results, and return an exit code."""
    pipeline = get_pipeline(pipeline_name)
    print(f"Executing pipeline '{pipeline.name}' on question: {question!r}\n")

    final_result: PipelineResult | None = None
    has_error = False

    for event in pipeline.stream(question):
        print(format_event_line(event))
        if event.type == "answer":
            final_result = PipelineResult.model_validate(event.data)
        elif event.type == "error":
            has_error = True

    if has_error or final_result is None:
        print("\nPipeline failed or terminated without producing an answer.")
        return 1

    print("\n--- Answer ---")
    print(final_result.answer.text)
    print("\n--- Citations ---")
    if final_result.answer.citations:
        for c in final_result.answer.citations:
            print(f"  - [{c.chunk_id}] {c.url}")
    else:
        print("  (None)")

    print(f"\nLLM calls: {final_result.llm_calls}")
    print(f"Latency: {final_result.latency_ms} ms")
    return 0


if __name__ == "__main__":
    main()
