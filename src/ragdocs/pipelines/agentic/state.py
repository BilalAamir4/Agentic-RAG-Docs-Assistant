"""Graph state, LLM output schemas and dependencies for the agentic pipelines (M10).

Runtime-safe: imports only pydantic, the standard library and ragdocs.schemas.
"""

import operator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field

from ragdocs.schemas import Answer, RetrievedChunk, TraceEvent

# Every decision TraceEvent carries data["outcome"] set to one of these (D25).
Outcome = Literal["ok", "retry", "stop", "info"]
OUTCOMES: frozenset[str] = frozenset({"ok", "retry", "stop", "info"})


class Grade(BaseModel):
    """The grader's verdict on one numbered excerpt."""

    index: int = Field(description="1-based excerpt number")
    relevant: bool = Field(description="True if the excerpt helps answer the question")
    reason: str = Field(description="Reason in at most 15 words")


class GradeBatch(BaseModel):
    """Structured grader output: one grade per excerpt."""

    grades: list[Grade]


class RewrittenQuery(BaseModel):
    """Structured rewriter output."""

    query: str = Field(description="Search query of at most 20 words")


class AgentState(TypedDict):
    """LangGraph state of the corrective (and later self-RAG) graph."""

    question: str
    query: str
    rewrites: int
    documents: list[RetrievedChunk]
    relevant: list[RetrievedChunk]
    web_docs: list[RetrievedChunk]
    used_web: bool
    answer: Answer | None
    diagnostics: dict[str, Any]
    contexts: list[RetrievedChunk]
    next_step: str | None
    events: Annotated[list[TraceEvent], operator.add]


def initial_state(question: str) -> AgentState:
    """Return the initial graph state for a question."""
    return AgentState(
        question=question,
        query=question,
        rewrites=0,
        documents=[],
        relevant=[],
        web_docs=[],
        used_web=False,
        answer=None,
        diagnostics={},
        contexts=[],
        next_step=None,
        events=[],
    )


@dataclass
class AgenticDeps:
    """Everything the graph nodes call; tests inject fakes.

    retriever has retrieve(query) -> list[RetrievedChunk]; grader_llm, rewriter_llm and
    generator_llm are structured runnables for GradeBatch, RewrittenQuery and
    AnswerDraft; web_search has search(query) -> list[dict]; settings is a Settings.
    """

    retriever: Any
    grader_llm: Any
    rewriter_llm: Any
    generator_llm: Any
    web_search: Any
    settings: Any
