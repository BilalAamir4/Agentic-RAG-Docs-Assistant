"""Deterministic per-item scores (M08 Step 2) and effective judge verdicts."""

import re
from dataclasses import dataclass
from pathlib import Path

from ragdocs.eval.metrics import evidence_recall_at_k, hit_at_k
from ragdocs.io_utils import read_jsonl
from ragdocs.schemas import (
    EvalItem,
    EvalRecord,
    ItemScores,
    JudgeRecord,
    JudgeVerdict,
    PipelineResult,
    TokenUsageRecord,
)

JUDGE_FILE_PATTERN = re.compile(r"^judge_v(\d+)\.jsonl$")


def must_mention_coverage(answer_text: str, must_mention: list[str]) -> float | None:
    """Share of must_mention identifiers found case-insensitively as substrings (D15)."""
    if not must_mention:
        return None
    lowered = answer_text.lower()
    found = sum(1 for term in must_mention if term.lower() in lowered)
    return found / len(must_mention)


def score_item(
    item: EvalItem, result: PipelineResult, usage: TokenUsageRecord, k: int
) -> ItemScores:
    """Compute the deterministic scores for one item.

    Contexts are the chunks given to the generator (D22). Fields that do not apply to
    the item's category are left as None.
    """
    abstained = result.answer.abstained
    scores = ItemScores(
        abstained=abstained,
        llm_calls=result.llm_calls,
        latency_ms=result.latency_ms,
        used_web=result.used_web,
        tokens_in=usage.tokens_in,
        tokens_out=usage.tokens_out,
    )
    if item.category == "unanswerable":
        scores.abstention_correct = abstained
        scores.hallucinated = not abstained
        return scores
    scores.false_abstention = abstained
    scores.context_hit_at_5 = hit_at_k(result.contexts, item.evidence, k)
    scores.context_evidence_recall_at_5 = evidence_recall_at_k(result.contexts, item.evidence, k)
    scores.must_mention_coverage = must_mention_coverage(result.answer.text, item.must_mention)
    return scores


def judge_eligible(item: EvalItem, result: PipelineResult) -> bool:
    """The judge runs on answerable, non-abstained items only."""
    return item.category != "unanswerable" and not result.answer.abstained


def latest_judge_file(run_dir: Path) -> tuple[int, Path] | None:
    """Return (version, path) of the highest judge_v<N>.jsonl in run_dir, or None."""
    found = [
        (int(m.group(1)), p)
        for p in Path(run_dir).iterdir()
        if p.is_file() and (m := JUDGE_FILE_PATTERN.match(p.name))
    ]
    return max(found) if found else None


@dataclass
class EffectiveVerdicts:
    """Verdicts each reader must use: from the highest judge file, else per_question."""

    verdicts: dict[str, JudgeVerdict]
    prompt_version: int | None
    judge_model: str | None
    source: str


def effective_verdicts(run_dir: Path, records: list[EvalRecord]) -> EffectiveVerdicts:
    """Return each item's verdict from the highest judge_v<N>.jsonl present.

    If no judge file exists, verdicts come from per_question.jsonl (the verdict field)
    and the version is unknown (None).
    """
    latest = latest_judge_file(run_dir)
    if latest is None:
        verdicts = {r.id: r.verdict for r in records if r.verdict is not None}
        return EffectiveVerdicts(verdicts, None, None, "per_question.jsonl")
    version, path = latest
    rows = [JudgeRecord.model_validate(r) for r in read_jsonl(path)]
    models = sorted({r.judge_model for r in rows})
    return EffectiveVerdicts(
        verdicts={r.id: r.verdict for r in rows},
        prompt_version=version,
        judge_model=", ".join(models) if models else None,
        source=path.name,
    )
