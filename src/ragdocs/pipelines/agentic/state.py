"""Graph state, LLM output schemas and dependencies for the agentic pipelines (M10, M11).

Runtime-safe: imports only pydantic, the standard library and ragdocs.schemas.
"""

import operator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, NotRequired, TypedDict

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


class RetrievalDecision(BaseModel):
    """Structured decide_retrieval output (M11 self-RAG)."""

    needs_docs: bool = Field(description="True if the documentation should be searched")
    reason: str = Field(description="Reason in at most 15 words")


class AnswerVerification(BaseModel):
    """Structured verify_answer output (M11 self-RAG).

    Length limits live in the descriptions only: a validator would turn an over-long
    claim into a parse failure and a D26 fallback.
    """

    grounded: bool = Field(description="True if every factual claim is supported by the excerpts")
    unsupported_claims: list[str] = Field(
        description="Each claim the excerpts do not support, quoting at most 20 words of it"
    )
    answers_question: bool = Field(description="True if the answer addresses the question")


class AgentState(TypedDict):
    """LangGraph state of the corrective and self-RAG graphs.

    needs_docs, regenerations and verification are self_rag fields; initial_state sets
    them only for mode "self_rag", so the corrective graph's input is unchanged from M10.
    """

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
    needs_docs: NotRequired[bool | None]
    regenerations: NotRequired[int]
    verification: NotRequired[dict[str, Any] | None]


def initial_state(question: str, mode: str = "corrective") -> AgentState:
    """Return the initial graph state for a question; mode "self_rag" adds its fields."""
    state = AgentState(
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
    if mode == "self_rag":
        state.update(needs_docs=None, regenerations=0, verification=None)
    return state


@dataclass
class AgenticDeps:
    """Everything the graph nodes call; tests inject fakes.

    retriever has retrieve(query) -> list[RetrievedChunk]; grader_llm, rewriter_llm and
    generator_llm are structured runnables for GradeBatch, RewrittenQuery and
    AnswerDraft; web_search has search(query) -> list[dict]; settings is a Settings.
    decider_llm and verifier_llm (self_rag only, M11) are structured runnables for
    RetrievalDecision and AnswerVerification on the grader model; corrective leaves
    them None.
    """

    retriever: Any
    grader_llm: Any
    rewriter_llm: Any
    generator_llm: Any
    web_search: Any
    settings: Any
    decider_llm: Any = None
    verifier_llm: Any = None
