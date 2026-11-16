"""Custom LLM judge for correctness and citation support (D9, D19, D20).

The judge works only from stored run data (per_question.jsonl), never regenerates
answers, and writes judge_v<N>.jsonl next to per_question.jsonl, where N is
Settings.judge_prompt_version. per_question.jsonl is never modified.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from diskcache import Cache
from langchain_core.messages import HumanMessage, SystemMessage

from ragdocs.config import Settings, get_settings
from ragdocs.eval.prompts import JUDGE_EXCERPT_TEMPLATE, JUDGE_PROMPT, JUDGE_USER_TEMPLATE
from ragdocs.schemas import EvalRecord, JudgeVerdict

PER_QUESTION_FILE = "per_question.jsonl"
CITED = "CITED"
NOT_CITED = "NOT CITED"


def judge_file_name(version: int) -> str:
    """Return the judge output file name for a prompt version."""
    return f"judge_v{version}.jsonl"


def cited_flags(record: EvalRecord) -> list[bool]:
    """Return one flag per context, True when the structured citations include it."""
    cited_ids = {c.chunk_id for c in record.result.answer.citations}
    return [rc.chunk.chunk_id in cited_ids for rc in record.result.contexts]


def format_judge_excerpts(record: EvalRecord) -> str:
    """Number every context excerpt in context order and mark it CITED or NOT CITED."""
    blocks: list[str] = []
    flags = cited_flags(record)
    pairs = zip(record.result.contexts, record.context_texts, strict=True)
    for idx, (rc, text) in enumerate(pairs):
        chunk = rc.chunk
        header = " > ".join([chunk.title, *chunk.heading_path])
        blocks.append(
            JUDGE_EXCERPT_TEMPLATE.format(
                n=idx + 1,
                flag=CITED if flags[idx] else NOT_CITED,
                header=header,
                url=chunk.url,
                text=text,
            )
        )
    return "\n\n".join(blocks)


def build_judge_messages(record: EvalRecord) -> list[Any]:
    """Return the system and user messages for one judge call."""
    user = JUDGE_USER_TEMPLATE.format(
        question=record.question,
        reference_answer=record.reference_answer or "",
        must_mention=", ".join(record.must_mention) or "(none)",
        answer=record.result.answer.text,
        excerpts=format_judge_excerpts(record),
    )
    return [SystemMessage(content=JUDGE_PROMPT), HumanMessage(content=user)]


def judge_cache_key(record: EvalRecord, settings: Settings) -> str:
    """sha1 of judge model, prompt version, question, answer, excerpts and cited flags."""
    payload = [
        settings.judge_model,
        settings.judge_prompt_version,
        record.question,
        record.result.answer.text,
        list(record.context_texts),
        cited_flags(record),
    ]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def open_judge_cache(settings: Settings) -> Cache:
    """Open the diskcache store for judge verdicts (cache/judge)."""
    return Cache(str(settings.cache_dir / "judge"))


def cached_verdict(record: EvalRecord, cache: Any, settings: Settings) -> JudgeVerdict | None:
    """Return the cached verdict for this record, or None."""
    raw = cache.get(judge_cache_key(record, settings))
    return JudgeVerdict.model_validate(raw) if raw is not None else None


def judge_item(
    record: EvalRecord,
    *,
    llm: Any = None,
    cache: Any = None,
    settings: Settings | None = None,
    callbacks: list[Any] | None = None,
) -> JudgeVerdict:
    """Judge one answerable, non-abstained record and return its verdict.

    Uses get_chat_model("judge").with_structured_output(JudgeVerdict) unless llm is
    given. A cache hit returns without calling the model.
    """
    settings = settings or get_settings()
    if cache is not None:
        hit = cached_verdict(record, cache, settings)
        if hit is not None:
            return hit
    if llm is None:
        from ragdocs.providers.llm import get_chat_model

        llm = get_chat_model("judge", settings).with_structured_output(JudgeVerdict)
    raw = llm.invoke(
        build_judge_messages(record),
        config={"callbacks": list(callbacks or []), "run_name": "judge"},
    )
    verdict = raw if isinstance(raw, JudgeVerdict) else JudgeVerdict.model_validate(raw)
    if cache is not None:
        cache.set(judge_cache_key(record, settings), verdict.model_dump())
    return verdict


def load_records(run_dir: Path) -> list[EvalRecord]:
    """Read and validate per_question.jsonl from a run folder."""
    from ragdocs.io_utils import read_jsonl

    return [EvalRecord.model_validate(r) for r in read_jsonl(Path(run_dir) / PER_QUESTION_FILE)]
