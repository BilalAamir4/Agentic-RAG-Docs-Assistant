"""Fakes for the corrective graph tests (M10 S2). No network.

ScriptedChatModel is a real BaseChatModel, so callbacks (CallCounter, test handlers)
see each call as a chat-model run; piping it into PydanticOutputParser makes a
structured runnable that raises OutputParserException on malformed output, like the
json_schema-bound ChatGroq.
"""

import json
from typing import Any

from eval_fakes import make_chunk
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, Field

from ragdocs.config import Settings
from ragdocs.generation.answer import AnswerDraft
from ragdocs.pipelines.agentic.pipeline import AgenticPipeline
from ragdocs.pipelines.agentic.state import AgenticDeps, GradeBatch, RewrittenQuery
from ragdocs.schemas import PipelineResult, RetrievedChunk, TraceEvent

QUESTION = "How do I add a checkpointer?"


class ScriptedChatModel(BaseChatModel):
    """Returns scripted message contents in order; records every message list received."""

    responses: list[str] = Field(default_factory=list)
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kw: Any
    ) -> ChatResult:
        self.received.append(list(messages))
        if not self.responses:
            raise AssertionError("ScriptedChatModel called more often than scripted")
        content = self.responses.pop(0)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def structured(model: ScriptedChatModel, schema: type[BaseModel]) -> Any:
    """Structured runnable: scripted chat model followed by a pydantic parser."""
    return model | PydanticOutputParser(pydantic_object=schema)


def grades(*flags: bool) -> str:
    """GradeBatch JSON grading excerpts 1..n with the given relevance flags."""
    rows = [{"index": i, "relevant": f, "reason": "r"} for i, f in enumerate(flags, start=1)]
    return json.dumps({"grades": rows})


def answer(cited: list[int] | None = None, abstain: bool = False) -> str:
    """AnswerDraft JSON."""
    return json.dumps(
        {"answer": "Use a checkpointer [1].", "cited": cited or [1], "abstain": abstain}
    )


def rewrite(query: str) -> str:
    """RewrittenQuery JSON."""
    return json.dumps({"query": query})


def chunks(*ids: int) -> list[RetrievedChunk]:
    """Retrieved chunks c<id>, ranked 1..n in the given order."""
    out = []
    for rank, i in enumerate(ids, start=1):
        rc = make_chunk(i)
        out.append(rc.model_copy(update={"rank": rank}))
    return out


class FakeRetriever:
    """Returns scripted chunk lists in order (the last one repeats); records queries."""

    def __init__(self, *batches: list[RetrievedChunk], error: Exception | None = None) -> None:
        self.batches = list(batches)
        self.queries: list[str] = []
        self.error = error

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.batches.pop(0) if len(self.batches) > 1 else self.batches[0]


class FakeWebSearch:
    """Returns fixed results; records queries."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.queries: list[str] = []

    def search(self, query: str) -> list[dict[str, Any]]:
        self.queries.append(query)
        return list(self.results)


WEB_RESULTS = [
    {
        "url": "https://docs.langchain.com/oss/python/langgraph/persistence",
        "title": "Persistence",
        "content": "Checkpointers save graph state.",
    },
    {
        "url": "https://docs.langchain.com/oss/python/langchain/human-in-the-loop",
        "title": "HITL",
        "content": "x" * 2500,
    },
]


class Harness:
    """A corrective pipeline wired to scripted fakes."""

    def __init__(
        self,
        retriever: FakeRetriever,
        grader: list[str],
        rewriter: list[str] | None = None,
        generator: list[str] | None = None,
        web: list[dict[str, Any]] | None = None,
        **settings: Any,
    ) -> None:
        self.retriever = retriever
        self.grader = ScriptedChatModel(responses=grader)
        self.rewriter = ScriptedChatModel(responses=rewriter or [])
        self.generator = ScriptedChatModel(responses=generator or [])
        self.web = FakeWebSearch(WEB_RESULTS if web is None else web)
        self.settings = Settings(_env_file=None, **settings)
        self.deps = AgenticDeps(
            retriever=retriever,
            grader_llm=structured(self.grader, GradeBatch),
            rewriter_llm=structured(self.rewriter, RewrittenQuery),
            generator_llm=structured(self.generator, AnswerDraft),
            web_search=self.web,
            settings=self.settings,
        )
        self.pipeline = AgenticPipeline("corrective", deps=self.deps)

    def run(self, callbacks: list[Any] | None = None) -> tuple[list[TraceEvent], PipelineResult]:
        """Stream the question; return all yielded events and the parsed result."""
        events = list(self.pipeline.stream(QUESTION, callbacks=callbacks))
        assert events[-1].type == "answer", events[-1]
        return events, PipelineResult.model_validate(events[-1].data)


def decisions(events: list[TraceEvent]) -> list[TraceEvent]:
    """Decision events only."""
    return [e for e in events if e.type == "decision"]


def node_path(events: list[TraceEvent]) -> list[str]:
    """Node names in node_start order."""
    return [e.node for e in events if e.type == "node_start"]
