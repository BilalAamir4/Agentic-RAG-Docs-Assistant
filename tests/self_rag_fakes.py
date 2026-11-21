"""Fakes for the self_rag graph tests (M11 S2). No network.

Reuses the corrective fakes (agentic_fakes) and adds a chat model whose script can hold
exceptions, plus JSON helpers for RetrievalDecision and AnswerVerification.
"""

import json
from typing import Any

import groq
import httpx
from agentic_fakes import (
    QUESTION,
    FakeRetriever,
    FakeWebSearch,
    ScriptedChatModel,
    structured,
)
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from ragdocs.config import Settings
from ragdocs.generation.answer import AnswerDraft
from ragdocs.pipelines.agentic.pipeline import AgenticPipeline
from ragdocs.pipelines.agentic.state import (
    AgenticDeps,
    AnswerVerification,
    GradeBatch,
    RetrievalDecision,
    RewrittenQuery,
)
from ragdocs.schemas import PipelineResult, TraceEvent

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
# Not JSON: the PydanticOutputParser raises OutputParserException (a D26 structured error).
MALFORMED = "this is not json"


class RaisingChatModel(ScriptedChatModel):
    """ScriptedChatModel whose responses may be exceptions, raised when reached."""

    responses: list[Any] = Field(default_factory=list)

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kw: Any
    ) -> ChatResult:
        self.received.append(list(messages))
        if not self.responses:
            raise AssertionError("RaisingChatModel called more often than scripted")
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=item))])


def decide(needs_docs: bool, reason: str = "about LangGraph") -> str:
    """RetrievalDecision JSON."""
    return json.dumps({"needs_docs": needs_docs, "reason": reason})


def verify(grounded: bool, claims: list[str] | None = None, answers: bool = True) -> str:
    """AnswerVerification JSON."""
    return json.dumps(
        {"grounded": grounded, "unsupported_claims": claims or [], "answers_question": answers}
    )


def rate_limit_error() -> groq.RateLimitError:
    """A groq 429, as raised after the client's own retries."""
    response = httpx.Response(429, request=REQUEST)
    return groq.RateLimitError("Error code: 429", response=response, body={"error": {}})


def connection_error() -> groq.APIConnectionError:
    """A groq transport failure."""
    return groq.APIConnectionError(request=REQUEST)


def json_validate_failed() -> groq.BadRequestError:
    """A groq 400 with error.code json_validate_failed (q049 in M10)."""
    body = {"error": {"type": "invalid_request_error", "code": "json_validate_failed"}}
    response = httpx.Response(400, request=REQUEST)
    return groq.BadRequestError("Error code: 400", response=response, body=body)


class SelfRagHarness:
    """A self_rag pipeline wired to scripted fakes; every model can raise scripted errors."""

    def __init__(
        self,
        retriever: FakeRetriever,
        decider: list[Any],
        grader: list[Any] | None = None,
        verifier: list[Any] | None = None,
        generator: list[Any] | None = None,
        rewriter: list[Any] | None = None,
        web: list[dict[str, Any]] | None = None,
        **settings: Any,
    ) -> None:
        self.retriever = retriever
        self.decider = RaisingChatModel(responses=decider)
        self.grader = RaisingChatModel(responses=grader or [])
        self.rewriter = RaisingChatModel(responses=rewriter or [])
        self.generator = RaisingChatModel(responses=generator or [])
        self.verifier = RaisingChatModel(responses=verifier or [])
        self.web = FakeWebSearch(web or [])
        self.settings = Settings(_env_file=None, **settings)
        self.deps = AgenticDeps(
            retriever=retriever,
            grader_llm=structured(self.grader, GradeBatch),
            rewriter_llm=structured(self.rewriter, RewrittenQuery),
            generator_llm=structured(self.generator, AnswerDraft),
            web_search=self.web,
            settings=self.settings,
            decider_llm=structured(self.decider, RetrievalDecision),
            verifier_llm=structured(self.verifier, AnswerVerification),
        )
        self.pipeline = AgenticPipeline("self_rag", deps=self.deps)

    @property
    def models(self) -> dict[str, RaisingChatModel]:
        """Every fake model by role."""
        return {
            "decide": self.decider,
            "grade": self.grader,
            "rewrite": self.rewriter,
            "generate": self.generator,
            "verify": self.verifier,
        }

    def calls(self) -> dict[str, int]:
        """Number of calls each fake model received."""
        return {role: len(m.received) for role, m in self.models.items()}

    def stream(self, question: str = QUESTION) -> list[TraceEvent]:
        """All yielded events."""
        return list(self.pipeline.stream(question))

    def run(self, question: str = QUESTION) -> tuple[list[TraceEvent], PipelineResult]:
        """Stream the question; return all yielded events and the parsed result."""
        events = self.stream(question)
        assert events[-1].type == "answer", events[-1]
        return events, PipelineResult.model_validate(events[-1].data)
