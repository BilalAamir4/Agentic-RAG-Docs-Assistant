"""Snapshot test: BaselinePipeline.stream output must not change when tracing is added.

The fixture tests/fixtures/baseline_stream_snapshot.json was generated from the M06
implementation (commit bfc7412) before any tracing code was added. Timing fields
(t_ms, latency_ms) are removed because they vary between runs.

Regenerate only on an intended behaviour change:
    .venv\\Scripts\\python tests\\test_baseline_snapshot.py --write
"""

import json
import sys
from pathlib import Path
from typing import Any

from ragdocs.generation.answer import AnswerDraft
from ragdocs.io_utils import read_text, write_text
from ragdocs.pipelines.baseline import BaselinePipeline
from ragdocs.schemas import Chunk, PipelineResult, RetrievedChunk

SNAPSHOT_PATH = Path(__file__).resolve().parent / "fixtures" / "baseline_stream_snapshot.json"
QUESTION = "Where do I set a bigger recursion limit?"
TIMING_KEYS = {"t_ms", "latency_ms"}


class _SnapshotLLM:
    """Stub StructuredLLM returning a fixed draft that cites one valid and one invalid excerpt."""

    def invoke(self, messages: Any, config: dict[str, Any] | None = None) -> AnswerDraft:
        """Return a fixed AnswerDraft without any network call."""
        return AnswerDraft(
            answer="Pass recursion_limit in the config [1]. Ignore this [7].",
            cited=[1, 7],
            abstain=False,
        )


class _SnapshotRetriever:
    """Stub retriever returning two fixed chunks."""

    mode = "hybrid"

    def retrieve(self, query: str, mode: str | None = None) -> list[RetrievedChunk]:
        """Return fixed chunks without touching the index."""
        return [_chunk("chk-a", "Graph API", 1, 0.91), _chunk("chk-b", "Errors", 2, 0.5)]


def _chunk(chunk_id: str, title: str, rank: int, score: float) -> RetrievedChunk:
    """Build a deterministic RetrievedChunk."""
    chunk = Chunk(
        chunk_id=chunk_id,
        doc_path=f"{chunk_id}.mdx",
        url=f"https://docs.langchain.com/{chunk_id}",
        title=title,
        heading_path=["Section"],
        anchor="sec",
        text=f"Text of {chunk_id}.",
        embed_text=f"{title}: Text of {chunk_id}.",
        n_tokens=5,
        has_code=False,
        source_commit="commit-1",
    )
    return RetrievedChunk(chunk=chunk, score=score, rank=rank, retriever="hybrid")


def _strip_timing(value: Any) -> Any:
    """Recursively remove timing keys from nested dicts and lists."""
    if isinstance(value, dict):
        return {k: _strip_timing(v) for k, v in value.items() if k not in TIMING_KEYS}
    if isinstance(value, list):
        return [_strip_timing(v) for v in value]
    return value


def build_snapshot() -> dict[str, Any]:
    """Run the baseline pipeline on stubs and return the timing-free snapshot."""
    pipeline = BaselinePipeline(retriever=_SnapshotRetriever(), structured_llm=_SnapshotLLM())
    events = list(pipeline.stream(QUESTION))
    result = PipelineResult.model_validate(events[-1].data)
    return {
        "events": [
            {"type": e.type, "node": e.node, "message": e.message, "data": _strip_timing(e.data)}
            for e in events[:-1]
        ]
        + [{"type": events[-1].type, "node": events[-1].node, "message": events[-1].message}],
        "result": _strip_timing(result.model_dump(mode="json")),
    }


def test_baseline_stream_matches_snapshot() -> None:
    """Events and final PipelineResult match the pre-tracing snapshot."""
    expected = json.loads(read_text(SNAPSHOT_PATH))
    actual = json.loads(json.dumps(build_snapshot()))
    assert actual == expected


if __name__ == "__main__" and "--write" in sys.argv:
    write_text(SNAPSHOT_PATH, json.dumps(build_snapshot(), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {SNAPSHOT_PATH}")
