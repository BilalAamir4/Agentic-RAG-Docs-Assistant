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


class WebResult(BaseModel):
    """One web search result kept after the docs-domain filter (M10)."""

    url: str
    title: str
    content: str


class WebSearchOutcome(BaseModel):
    """Web search results plus the diagnostics of the defensive domain filter (M10)."""

    query: str
    results: list[WebResult]
    raw_urls: list[str] = Field(default_factory=list)
    dropped_off_domain: list[str] = Field(default_factory=list)


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
    # Pipeline diagnostics (M11). Only self_rag fills it (diagnostics["fallbacks"]:
    # decide_failed, verify_failed, regenerate_failed). Left out of dumps when empty, so
    # baseline and corrective results serialise exactly as before M11.
    diagnostics: dict[str, Any] = Field(default_factory=dict, exclude_if=lambda v: not v)


# Evaluation records (M08). Written by ragdocs.eval.runner, read by report, compare and
# the judge. Defined here so every reader validates the same shape.

JUDGE_RATIONALE_MAX_WORDS = 60


class ModelTokenUsage(BaseModel):
    """Token counts and call count for one model."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    usage_missing: int = 0


class TokenUsageRecord(BaseModel):
    """Token usage summed over all models plus a per-model breakdown."""

    tokens_in: int = 0
    tokens_out: int = 0
    usage_missing: int = 0
    by_model: dict[str, ModelTokenUsage] = Field(default_factory=dict)


class JudgeVerdict(BaseModel):
    """Structured verdict returned by the custom LLM judge."""

    correctness: Literal[0, 1, 2] = Field(
        description="2 correct, 1 partly correct or incomplete, 0 wrong or contradicting"
    )
    citation_support: Literal[0, 1] = Field(
        description="1 if every cited excerpt supports a claim and no central claim is uncited"
    )
    rationale: str = Field(
        description=f"Short justification of at most {JUDGE_RATIONALE_MAX_WORDS} words"
    )

    @field_validator("rationale")
    @classmethod
    def limit_rationale(cls, v: str) -> str:
        """Truncate the rationale to the word limit instead of failing the verdict."""
        words = v.split()
        return " ".join(words[:JUDGE_RATIONALE_MAX_WORDS])


class FailedAttempt(BaseModel):
    """One pipeline attempt that ended in an error event before the item succeeded."""

    stage: str
    message: str
    utc: str
    # Error kind (ragdocs.providers.errors.ErrorKind), set by the runner from M11 S1;
    # None in older runs, whose kind is classified from the message.
    kind: str | None = None


class ErrorReclassification(BaseModel):
    """One evidence-backed error-kind override for a stored failed attempt (M11 S1).

    run is the run folder (repository-relative, forward slashes; matched by folder name),
    item the eval id, kind the corrected kind, evidence where the kind is shown, and utc,
    when set, the failed attempt's utc (otherwise every failed attempt of the item).
    """

    run: str
    item: str
    kind: Literal["structured_output", "rate_limit", "transient", "permanent", "unclassified"]
    evidence: list[str] = Field(min_length=1)
    utc: str | None = None


class ItemScores(BaseModel):
    """Deterministic per-item scores; fields that do not apply to a category are None."""

    model_config = {"populate_by_name": True}

    abstained: bool
    abstention_correct: bool | None = None
    hallucinated: bool | None = None
    false_abstention: bool | None = None
    context_hit_at_5: float | None = Field(default=None, alias="context_hit@5")
    context_evidence_recall_at_5: float | None = Field(
        default=None, alias="context_evidence_recall@5"
    )
    must_mention_coverage: float | None = None
    llm_calls: int
    latency_ms: int
    used_web: bool
    tokens_in: int
    tokens_out: int
    # Failed attempts before success whose kind is structured_output (M08, D23; counted
    # by kind since M11 S1, ragdocs.eval.failures); None in runs made before the field.
    structured_output_failures: int | None = None
    # Failed attempts caused by provider rate limits (not counted above).
    rate_limited_attempts: int | None = None
    # Other failed attempts by kind (M11 S1); None in runs made before the fields.
    transient_call_errors: int | None = None
    permanent_call_errors: int | None = None
    unclassified_call_errors: int | None = None


class EvalRecord(BaseModel):
    """One line of per_question.jsonl."""

    id: str
    category: Literal["single", "multi", "version", "unanswerable"]
    question: str
    reference_answer: str | None
    evidence: list[Evidence]
    must_mention: list[str]
    result: PipelineResult
    context_texts: list[str]
    usage: TokenUsageRecord
    langsmith_run_id: str | None
    scores: ItemScores
    judge_eligible: bool
    verdict: JudgeVerdict | None = None
    failed_attempts: list[FailedAttempt] = Field(default_factory=list)


class JudgeRecord(BaseModel):
    """One line of judge_v<N>.jsonl."""

    id: str
    verdict: JudgeVerdict
    judge_model: str
    judge_prompt_version: int
    usage: TokenUsageRecord = Field(default_factory=TokenUsageRecord)
    cached: bool = False
