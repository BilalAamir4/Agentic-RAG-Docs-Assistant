"""Answer draft modeling, context formatting, and citation validation."""

import re
from collections.abc import Sequence
from typing import Any, Literal, Protocol, runtime_checkable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ragdocs.generation.prompts import (
    ABSTAIN_TEXT,
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_TEMPLATE,
)
from ragdocs.schemas import Answer, Chunk, Citation, RetrievedChunk


class AnswerDraft(BaseModel):
    """Structured LLM output draft before citation validation."""

    answer: str = Field(description="The generated answer text")
    cited: list[int] = Field(
        default_factory=list,
        description="List of 1-based excerpt numbers cited in the answer",
    )
    abstain: bool = Field(
        default=False,
        description="True if excerpts do not contain enough information to answer",
    )


@runtime_checkable
class StructuredLLM(Protocol):
    """Protocol for structured output LLMs generating AnswerDraft."""

    def invoke(self, messages: Any, **kwargs: Any) -> AnswerDraft:
        """Invoke structured model with chat messages."""
        ...


def build_structured_llm(
    chat_model: BaseChatModel,
    method: Literal["function_calling", "json_schema"] = "function_calling",
    strict: bool | None = None,
) -> StructuredLLM:
    """Bind the AnswerDraft schema to the chat model with the given structured-output method.

    method="json_schema" with strict=True uses Groq's constrained decoding (see D23).
    """
    if method == "json_schema":
        return chat_model.with_structured_output(AnswerDraft, method=method, strict=strict)
    return chat_model.with_structured_output(AnswerDraft, method=method)


def _extract_chunk(c: RetrievedChunk | Chunk) -> Chunk:
    """Return inner Chunk instance from RetrievedChunk or Chunk."""
    return c.chunk if isinstance(c, RetrievedChunk) else c


def format_context(chunks: Sequence[RetrievedChunk | Chunk]) -> str:
    """Format documentation chunks into numbered context blocks.

    Format per chunk:
        "[n] {title} > {heading path joined by ' > '} ({url})" on one line,
        followed by the chunk text. Blocks are separated by a blank line.
    """
    blocks: list[str] = []
    for idx, raw_chunk in enumerate(chunks):
        n = idx + 1
        c = _extract_chunk(raw_chunk)
        if c.heading_path:
            header = f"{c.title} > {' > '.join(c.heading_path)}"
        else:
            header = c.title
        blocks.append(f"[{n}] {header} ({c.url})\n{c.text}")
    return "\n\n".join(blocks)


def validate_answer(
    draft: AnswerDraft,
    chunks: Sequence[RetrievedChunk | Chunk],
) -> tuple[Answer, dict[str, Any]]:
    """Validate and sanitize an AnswerDraft against the candidate chunks.

    Rules:
    1. Citation numbers outside 1..len(chunks) are dropped and counted in dropped_citations.
    2. Duplicate citation numbers are removed while preserving order.
    3. [n] markers in answer text pointing to dropped numbers are removed from the text.
    4. If abstain is True (or answer is exactly ABSTAIN_TEXT), text is forced to ABSTAIN_TEXT
       and citations are emptied.
    5. Citation entries are built from valid chunk indices.
    6. Diagnostics include dropped_citations count and uncited flag (True when not abstaining
       and no valid citations remain).

    Returns:
        tuple of (Answer, diagnostics_dict)
    """
    valid_range = set(range(1, len(chunks) + 1))

    # Identify dropped citation numbers from cited list
    dropped_citations = sum(1 for c in draft.cited if c not in valid_range)

    # Collect valid unique citations preserving first-seen order
    valid_cited: list[int] = []
    seen: set[int] = set()
    for c in draft.cited:
        if c in valid_range and c not in seen:
            valid_cited.append(c)
            seen.add(c)

    # Identify all invalid markers present in cited or in answer text
    dropped_numbers = {c for c in draft.cited if c not in valid_range}
    for match in re.finditer(r"\[(\d+)\]", draft.answer):
        num = int(match.group(1))
        if num not in valid_range:
            dropped_numbers.add(num)

    # Remove invalid markers from the text
    cleaned_text = draft.answer
    for num in dropped_numbers:
        cleaned_text = re.sub(rf"\[{num}\]", "", cleaned_text)

    # Normalize whitespace and spacing before punctuation
    cleaned_text = re.sub(r" +([.,;!?])", r"\1", cleaned_text)
    cleaned_text = re.sub(r"  +", " ", cleaned_text).strip()

    # Check abstention status
    is_abstained = draft.abstain or (cleaned_text == ABSTAIN_TEXT)

    if is_abstained:
        final_text = ABSTAIN_TEXT
        final_citations: list[Citation] = []
        uncited = False
    else:
        final_text = cleaned_text
        final_citations = []
        for c_idx in valid_cited:
            c = _extract_chunk(chunks[c_idx - 1])
            final_citations.append(Citation(chunk_id=c.chunk_id, url=c.url))
        uncited = len(final_citations) == 0

    diagnostics = {
        "dropped_citations": dropped_citations,
        "uncited": uncited,
    }

    return (
        Answer(
            text=final_text,
            citations=final_citations,
            abstained=is_abstained,
        ),
        diagnostics,
    )


def generate_answer(
    question: str,
    chunks: Sequence[RetrievedChunk | Chunk],
    llm: StructuredLLM,
) -> tuple[Answer, dict[str, Any]]:
    """Build messages from prompts, invoke structured LLM, and validate answer."""
    context = format_context(chunks)
    messages = [
        SystemMessage(content=ANSWER_SYSTEM_PROMPT),
        HumanMessage(content=ANSWER_USER_TEMPLATE.format(question=question, context=context)),
    ]
    draft = llm.invoke(messages)
    return validate_answer(draft, chunks)
