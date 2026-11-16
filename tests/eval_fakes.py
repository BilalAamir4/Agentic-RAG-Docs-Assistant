"""Fakes shared by the M08 eval tests: items, pipeline, judge LLM, clock. No network."""

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from ragdocs.config import Settings
from ragdocs.generation.prompts import ABSTAIN_TEXT
from ragdocs.io_utils import write_jsonl
from ragdocs.schemas import (
    Answer,
    Chunk,
    Citation,
    EvalItem,
    JudgeVerdict,
    PipelineResult,
    RetrievedChunk,
    TraceEvent,
)

GEN_MODEL = "openai/gpt-oss-120b"


def make_chunk(i: int, doc_path: str = "doc.mdx", anchor: str | None = None) -> RetrievedChunk:
    """Deterministic RetrievedChunk number i."""
    chunk = Chunk(
        chunk_id=f"c{i}",
        doc_path=doc_path,
        url=f"https://docs.langchain.com/c{i}",
        title=f"Title {i}",
        heading_path=[f"H{i}"],
        anchor=anchor or f"a{i}",
        text=f"Text of chunk {i}.",
        embed_text="",
        n_tokens=4,
        has_code=False,
        source_commit="x",
    )
    return RetrievedChunk(chunk=chunk, score=1.0 / i, rank=i, retriever="hybrid")


def make_items() -> list[EvalItem]:
    """Four items: single, multi, version, unanswerable (q004 answers wrongly)."""
    ev = [{"doc_path": "doc.mdx", "anchor": "a2"}]
    base = {"source": "synthetic", "verified": True}
    return [
        EvalItem(
            id="q001",
            question="Q1?",
            category="single",
            reference_answer="R1",
            evidence=ev,
            must_mention=["StateGraph", "add_node"],
            **base,
        ),
        EvalItem(
            id="q002",
            question="Q2?",
            category="multi",
            reference_answer="R2",
            evidence=ev + [{"doc_path": "other.mdx", "anchor": "z"}],
            must_mention=["Send"],
            **base,
        ),
        EvalItem(
            id="q003",
            question="Q3?",
            category="version",
            reference_answer="R3",
            evidence=ev,
            must_mention=["x"],
            **base,
        ),
        EvalItem(id="q004", question="Q4?", category="unanswerable", **base),
    ]


def write_eval_set(tmp_path: Path, items: list[EvalItem] | None = None) -> tuple[Path, str]:
    """Write items to a JSONL eval set and return (path, sha256)."""
    path = tmp_path / "eval_set.jsonl"
    write_jsonl(path, [i.model_dump(mode="json") for i in (items or make_items())])
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    """Settings pointing at tmp_path, not reading .env."""
    eval_path, sha = write_eval_set(tmp_path)
    values: dict[str, Any] = {
        "eval_path": eval_path,
        "eval_set_sha256": sha,
        "cache_dir": tmp_path / "cache",
        "results_dir": tmp_path / "results",
        "index_dir": tmp_path / "index",
        "langsmith_tracing": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


# Answers per question: (text, cited context numbers, abstained)
DEFAULT_ANSWERS: dict[str, tuple[str, list[int], bool]] = {
    "Q1?": ("Use stategraph and ADD_NODE.", [2], False),
    "Q2?": ("Use Send.", [1, 2], False),
    "Q3?": (ABSTAIN_TEXT, [], True),
    "Q4?": ("Made up answer.", [1], False),
}


def emit_usage(callbacks: list[Any], model: str, tokens_in: int, tokens_out: int) -> None:
    """Simulate one chat-model call reporting usage to the handlers."""
    run_id = uuid4()
    msg = AIMessage(
        content="",
        usage_metadata={
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        },
        response_metadata={"model_name": model},
    )
    for cb in callbacks:
        cb.on_chat_model_start({}, [[]], run_id=run_id, metadata={"ls_model_name": model})
        cb.on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]), run_id=run_id)


class FakePipeline:
    """Pipeline returning fixed answers and contexts [c1, c2, c3]; records calls."""

    name = "fake"

    def __init__(self, answers: dict[str, tuple[str, list[int], bool]] | None = None) -> None:
        self.answers = answers or DEFAULT_ANSWERS
        self.questions: list[str] = []
        self.fail_on: set[str] = set()
        self.fail_message = "BadRequestError: 400"

    def stream(
        self,
        question: str,
        run_metadata: dict[str, Any] | None = None,
        callbacks: list[Any] | None = None,
    ) -> Any:
        """Yield one answer event (or an error event for questions in fail_on)."""
        self.questions.append(question)
        emit_usage(callbacks or [], GEN_MODEL, 1000, 200)
        if question in self.fail_on:
            yield TraceEvent(type="node_start", node="generate", message="gen", t_ms=0)
            message = self.fail_message
            yield TraceEvent(type="error", node="error", message=message, t_ms=1)
            return
        text, cited, abstained = self.answers[question]
        contexts = [make_chunk(i) for i in (1, 2, 3)]
        citations = [
            Citation(chunk_id=f"c{n}", url=f"https://docs.langchain.com/c{n}") for n in cited
        ]
        result = PipelineResult(
            question=question,
            pipeline=self.name,
            answer=Answer(text=text, citations=citations, abstained=abstained),
            contexts=contexts,
            trace=[],
            llm_calls=1,
            latency_ms=100 * (len(self.questions)),
        )
        yield TraceEvent(
            type="answer", node="answer", message="done", data=result.model_dump(), t_ms=5
        )


class FakeJudgeLLM:
    """Structured judge stub returning a fixed verdict and reporting usage."""

    def __init__(self, verdict: JudgeVerdict | None = None, fail_times: int = 0) -> None:
        self.verdict = verdict or JudgeVerdict(correctness=2, citation_support=1, rationale="ok")
        self.calls: list[Any] = []
        self.fail_times = fail_times

    def invoke(self, messages: Any, config: dict[str, Any] | None = None) -> JudgeVerdict:
        """Record the messages and return the verdict (or raise for fail_times calls)."""
        self.calls.append(messages)
        emit_usage((config or {}).get("callbacks", []), "gemini-3.5-flash-lite", 900, 60)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("judge provider error")
        return self.verdict


class FakeClock:
    """Manual clock; sleep advances time."""

    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        """Advance time instead of sleeping."""
        self.sleeps.append(seconds)
        self.t += seconds
