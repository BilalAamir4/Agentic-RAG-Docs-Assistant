"""Pydantic data models for the ragdocs pipeline."""

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class Chunk(BaseModel):
    """A chunk of documentation extracted from source documents."""

    chunk_id: str
    doc_path: str
    url: str
    title: str
    heading_path: list[str]
    anchor: str
    text: str
    embed_text: str
    n_tokens: int
    has_code: bool
    source_commit: str

    @field_validator("doc_path")
    @classmethod
    def normalize_doc_path(cls, v: str) -> str:
        """Ensure doc_path always uses forward slashes."""
        return v.replace("\\", "/")


class Evidence(BaseModel):
    """Ground-truth documentation reference supporting an answer."""

    doc_path: str
    anchor: str

    @field_validator("doc_path")
    @classmethod
    def normalize_doc_path(cls, v: str) -> str:
        """Ensure doc_path always uses forward slashes."""
        return v.replace("\\", "/")


class EvalItem(BaseModel):
    """An evaluation dataset item with questions and gold standard references."""

    id: str = Field(pattern=r"^q\d{3}$")
    question: str
    category: Literal["single", "multi", "version", "unanswerable"]
    reference_answer: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    must_mention: list[str] = Field(default_factory=list)
    source: str
    notes: str = ""
    verified: bool = False

    @model_validator(mode="after")
    def validate_eval_item(self) -> Self:
        """Validate answer and evidence constraints based on item category."""
        if self.category == "unanswerable":
            if self.reference_answer is not None:
                raise ValueError("Unanswerable items must have reference_answer set to None")
            if len(self.evidence) > 0:
                raise ValueError("Unanswerable items must have empty evidence")
        else:
            if not self.reference_answer or not self.reference_answer.strip():
                raise ValueError(f"{self.category} items must have a non-empty reference_answer")
            if len(self.evidence) == 0:
                raise ValueError(f"{self.category} items must have at least one evidence entry")
        return self


class RetrievedChunk(BaseModel):
    """A chunk scored and ranked by a retrieval algorithm."""

    chunk: Chunk
    score: float
    rank: int
    retriever: str


class Citation(BaseModel):
    """A citation reference linking an answer statement to source documentation."""

    chunk_id: str
    url: str


class Answer(BaseModel):
    """An answer returned by a pipeline with citations and abstention status."""

    text: str
    citations: list[Citation]
    abstained: bool


class TraceEvent(BaseModel):
    """A single diagnostic event emitted during pipeline execution."""

    type: Literal["node_start", "node_end", "decision", "retrieval", "answer", "error"]
    node: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    t_ms: int


class PipelineResult(BaseModel):
    """Complete result of a pipeline execution over a question."""

    question: str
    pipeline: str
    answer: Answer
    contexts: list[RetrievedChunk]
    trace: list[TraceEvent]
    llm_calls: int
    latency_ms: int
    used_web: bool = False
