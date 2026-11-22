"""Request models, question validation and error bodies for the API."""

from typing import Literal

from pydantic import BaseModel

PipelineName = Literal["baseline", "corrective", "self_rag"]

MIN_QUESTION_CHARS = 3
ALLOWED_CONTROL_CHARS = frozenset("\n\t")

ERR_BAD_JSON = 'Send JSON with a "question" string.'
ERR_CONTROL = "The question contains unsupported control characters."
ERR_PIPELINE = "Unknown pipeline. Choose baseline, corrective or self_rag."
ERR_TOO_LARGE = "Request body too large."
ERR_INTERNAL = "Internal error."


def err_length(max_chars: int) -> str:
    """Return the length error message for the configured maximum."""
    return f"The question must be between {MIN_QUESTION_CHARS} and {max_chars} characters."


class AskRequest(BaseModel):
    """Body of POST /api/ask."""

    question: str
    pipeline: PipelineName = "self_rag"


class QuestionError(Exception):
    """A question failed validation; the message is the exact client-facing text."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def validate_question(raw: str, max_chars: int) -> str:
    """Strip the question and check length and control characters.

    Raises QuestionError with the client-facing message on failure.
    """
    text = raw.strip()
    if not MIN_QUESTION_CHARS <= len(text) <= max_chars:
        raise QuestionError(err_length(max_chars))
    for ch in text:
        code = ord(ch)
        if (code < 32 or code == 127) and ch not in ALLOWED_CONTROL_CHARS:
            raise QuestionError(ERR_CONTROL)
    return text
