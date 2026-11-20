"""Fixture test: the messages generate_answer sends must not change (M11 S1).

tests/fixtures/generate_answer_messages.json was written from generate_answer at commit
06b2383, before the extra_messages parameter was added. Each entry is the message role
(LangChain message type) and content, in send order.

Regenerate only on an intended change to the shared answer prompt (needs a DECISIONS.md
entry):
    .venv\\Scripts\\python tests\\test_generate_answer_messages.py --write
"""

import json
import sys
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from ragdocs.generation.answer import AnswerDraft, generate_answer
from ragdocs.io_utils import read_text, write_text
from ragdocs.schemas import Chunk, RetrievedChunk

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "generate_answer_messages.json"
QUESTION = "Where do I set a bigger recursion limit?"


class _RecordingLLM:
    """Fake structured LLM that records the messages it receives."""

    def __init__(self) -> None:
        self.received: list[BaseMessage] = []

    def invoke(self, messages: Any, **kwargs: Any) -> AnswerDraft:
        """Record messages and return a fixed draft without any network call."""
        self.received = list(messages)
        return AnswerDraft(answer="Pass recursion_limit in the config [1].", cited=[1])


def _chunk(chunk_id: str, title: str, heading: list[str], rank: int) -> RetrievedChunk:
    """Build a deterministic RetrievedChunk."""
    chunk = Chunk(
        chunk_id=chunk_id,
        doc_path=f"{chunk_id}.mdx",
        url=f"https://docs.langchain.com/oss/python/langgraph/{chunk_id}",
        title=title,
        heading_path=heading,
        anchor="sec",
        text=f"Text of {chunk_id}.\nSecond line with `code`.",
        embed_text=f"{title}: Text of {chunk_id}.",
        n_tokens=9,
        has_code=True,
        source_commit="commit-1",
    )
    return RetrievedChunk(chunk=chunk, score=1.0 / rank, rank=rank, retriever="hybrid")


CONTEXTS = [
    _chunk("graph-api", "Graph API", ["Recursion limit"], 1),
    _chunk("errors", "Errors", [], 2),
]


def as_rows(messages: list[BaseMessage]) -> list[dict[str, str]]:
    """Role and content of each message, in order."""
    return [{"role": m.type, "content": str(m.content)} for m in messages]


def sent_messages(extra: list[BaseMessage] | None = None, pass_extra: bool = False) -> list:
    """Run generate_answer on the fixed inputs and return the recorded messages."""
    llm = _RecordingLLM()
    if pass_extra:
        generate_answer(QUESTION, CONTEXTS, llm, extra_messages=extra)
    else:
        generate_answer(QUESTION, CONTEXTS, llm)
    return llm.received


def _fixture() -> list[dict[str, str]]:
    return json.loads(read_text(FIXTURE_PATH))


def _dumped(rows: list[dict[str, str]]) -> str:
    return json.dumps(rows, indent=2, ensure_ascii=False) + "\n"


def test_default_messages_match_fixture_byte_for_byte() -> None:
    assert _dumped(as_rows(sent_messages())) == read_text(FIXTURE_PATH)


def test_extra_messages_none_matches_fixture() -> None:
    assert _dumped(as_rows(sent_messages(None, pass_extra=True))) == read_text(FIXTURE_PATH)


def test_extra_messages_are_appended_in_order() -> None:
    extra: list[BaseMessage] = [
        AIMessage(content="Previous answer."),
        HumanMessage(content="The verifier rejected it; answer again."),
    ]
    rows = as_rows(sent_messages(extra, pass_extra=True))
    assert rows == _fixture() + as_rows(extra)


if __name__ == "__main__" and "--write" in sys.argv:
    write_text(FIXTURE_PATH, _dumped(as_rows(sent_messages())))
    print(f"Wrote {FIXTURE_PATH}")
