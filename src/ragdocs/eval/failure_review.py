"""Failure labels and the human review file (M15, offline).

A failed item is an answerable item with correctness below 2 (a false abstention counts as
0, as in the summary) or an unanswerable item that was hallucinated. Each gets the first
label of AUTO_LABELS that applies; items no rule covers get "needs_label" and a proposed
label from PROPOSAL_LABELS, chosen from the trace, the judge rationale and the RAGAS
faithfulness score. Everything is read from a committed run folder; the output is
deterministic.
"""

import csv
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ragdocs.eval.judge import load_records
from ragdocs.eval.report import correctness_of, first_retrieval_hit_at_5
from ragdocs.eval.scoring import EffectiveVerdicts, effective_verdicts
from ragdocs.io_utils import read_jsonl, write_text
from ragdocs.schemas import EvalRecord, Evidence, JudgeVerdict

PIPELINE_ORDER = ("baseline", "corrective", "self_rag")
FILTERING_PIPELINES = ("corrective", "self_rag")
RAGAS_SCORES_FILE = "ragas_scores.jsonl"
CSV_COLUMNS = (
    "pipeline",
    "id",
    "category",
    "correctness",
    "auto_label",
    "auto_reason",
    "proposed_label",
    "final_label",
    "note",
    "ragas_faithfulness",
)
NEEDS_LABEL = "needs_label"
ANSWER_CHARS = 600
LOW_FAITHFULNESS = 0.8
SCORE_DIGITS = 3
GRADING_COUNTERS = ("grading_failures", "missing_grades", "invalid_grades")
REWRITE_NODE = "rewrite_query"
REGENERATE_NODE = "regenerate"
OUT_OF_SCOPE_NODE = "out_of_scope"

# (label, one-line definition), in order of precedence.
AUTO_LABELS: list[tuple[str, str]] = [
    ("router_out_of_scope", "Self-RAG routed an answerable question out of scope."),
    (
        "structured_output_failure",
        "A structured call failed or fell back on the path that produced the outcome.",
    ),
    ("retrieval_miss", "No gold evidence in the first retrieval's top 5."),
    (
        "grading_drop",
        "Gold evidence was in the first retrieval but not in the contexts given to the generator.",
    ),
    ("false_abstention", "Answerable question, the pipeline abstained."),
    ("hallucinated_unanswerable", "Unanswerable question, the pipeline answered."),
    ("web_used_failure", "Web search results were used and the answer still failed."),
]
PROPOSAL_LABELS: list[tuple[str, str]] = [
    ("rewrite_drift", "The rewritten query moved away from what the question asked."),
    ("stale_web_content", "The answer relied on web content that is out of date."),
    ("unfaithful_generation", "The answer states something its excerpts do not support."),
    ("incomplete_answer", "The answer is right as far as it goes but omits a needed fact."),
    ("verifier_false_alarm", "The verifier rejected a good answer and regeneration made it worse."),
    ("judge_disagreement", "The judge's verdict looks wrong against the reference answer."),
]
UNFAITHFUL_PATTERN = re.compile(
    r"\binvent|fabricat|hallucinat|not (?:in|supported by) (?:the |any )?excerpt|unsupported",
    re.IGNORECASE,
)
INCOMPLETE_PATTERN = re.compile(
    r"\bomit|\bmiss(?:es|ing)\b|incomplete|does not (?:mention|explain|cover)|lacks?\b",
    re.IGNORECASE,
)


@dataclass
class FailureCase:
    """One CSV row plus the record it came from (for the review file)."""

    pipeline: str
    record: EvalRecord
    correctness: int | None
    auto_label: str
    auto_reason: str
    proposed_label: str
    final_label: str
    note: str
    faithfulness: float | None
    verdict: JudgeVerdict | None


def evidence_names(evidence: list[Evidence]) -> str:
    """Gold evidence as 'doc_path#anchor' joined by ', '."""
    return ", ".join(f"{e.doc_path}#{e.anchor}" for e in evidence)


def is_failed(record: EvalRecord, correctness: int | None) -> bool:
    """True for an answerable item below correctness 2 or a hallucinated unanswerable item."""
    if record.category == "unanswerable":
        return bool(record.scores.hallucinated)
    return correctness is None or correctness < 2


def _structured_reason(record: EvalRecord) -> str | None:
    """Evidence of a failed structured call or fallback on the item's path, else None."""
    diag = record.result.diagnostics
    if diag.get("fallbacks"):
        return f"diagnostics fallbacks: {', '.join(str(f) for f in diag['fallbacks'])}"
    for counter in GRADING_COUNTERS:
        if diag.get(counter):
            return f"diagnostics {counter} = {diag[counter]}"
    for event in record.result.trace:
        if event.type == "decision" and (
            event.data.get("fallback") or event.data.get("grading_failed")
        ):
            return f"trace {event.node}: {event.message}"
    return None


def auto_label(
    record: EvalRecord, correctness: int | None, refs: Mapping[str, Evidence] | None = None
) -> tuple[str, str]:
    """First applicable automatic label and its evidence, or (NEEDS_LABEL, '')."""
    answerable = record.category != "unanswerable"
    result = record.result
    names = evidence_names(record.evidence)
    if answerable and any(e.node == OUT_OF_SCOPE_NODE for e in result.trace):
        return "router_out_of_scope", "decide_retrieval routed the question to out_of_scope"
    reason = _structured_reason(record)
    if reason:
        return "structured_output_failure", reason
    if answerable and first_retrieval_hit_at_5(record, refs) == 0:
        return "retrieval_miss", f"gold anchor {names} not in first top 5"
    if answerable and result.pipeline in FILTERING_PIPELINES and not record.scores.context_hit_at_5:
        return "grading_drop", f"gold anchor {names} in first top 5, not in generator contexts"
    if answerable and record.scores.abstained:
        return "false_abstention", "abstained although the documentation answers it"
    if not answerable and record.scores.hallucinated:
        return "hallucinated_unanswerable", "answered an unanswerable question"
    if result.used_web:
        return "web_used_failure", "used_web is true"
    return NEEDS_LABEL, ""


def _faithfulness_text(faithfulness: float | None) -> str:
    """Sentence on RAGAS faithfulness for a note."""
    if faithfulness is None:
        return "RAGAS faithfulness not scored."
    if faithfulness < LOW_FAITHFULNESS:
        return f"RAGAS faithfulness {faithfulness:.{SCORE_DIGITS}f} (low) supports this."
    return (
        f"RAGAS faithfulness {faithfulness:.{SCORE_DIGITS}f} does not flag it "
        "(a prose-level signal that does not check code blocks, D19)."
    )


def propose_label(
    record: EvalRecord, verdict: JudgeVerdict | None, faithfulness: float | None
) -> tuple[str, str]:
    """Proposed label and the evidence for it, for an item no automatic rule covers."""
    nodes = {e.node for e in record.result.trace}
    rationale = verdict.rationale if verdict else ""
    quote = f'Judge: "{rationale}"'
    if REWRITE_NODE in nodes:
        return "rewrite_drift", f"The query was rewritten before the answer. {quote}"
    if REGENERATE_NODE in nodes:
        return "verifier_false_alarm", f"The verifier triggered a regeneration. {quote}"
    if UNFAITHFUL_PATTERN.search(rationale):
        return "unfaithful_generation", f"{quote} {_faithfulness_text(faithfulness)}"
    if INCOMPLETE_PATTERN.search(rationale):
        return "incomplete_answer", f"{quote} {_faithfulness_text(faithfulness)}"
    return "judge_disagreement", f"No other rule matched. {quote}"


def faithfulness_by_id(run_dir: Path) -> dict[str, float]:
    """RAGAS faithfulness per item id from ragas_scores.jsonl (items without a score left out)."""
    path = Path(run_dir) / RAGAS_SCORES_FILE
    rows = read_jsonl(path) if path.is_file() else []
    return {r["id"]: float(r["faithfulness"]) for r in rows if r.get("faithfulness") is not None}


def build_case(
    pipeline: str,
    record: EvalRecord,
    ev: EffectiveVerdicts,
    faith: Mapping[str, float],
    refs: Mapping[str, Evidence] | None = None,
) -> FailureCase | None:
    """The failure case for a record, or None when the item did not fail."""
    correctness = correctness_of(record, ev) if record.category != "unanswerable" else None
    if not is_failed(record, correctness):
        return None
    label, reason = auto_label(record, correctness, refs)
    verdict = ev.verdicts.get(record.id)
    score = faith.get(record.id)
    proposed = note = final = ""
    if label == NEEDS_LABEL:
        proposed, note = propose_label(record, verdict, score)
    else:
        final = label
    return FailureCase(
        pipeline, record, correctness, label, reason, proposed, final, note, score, verdict
    )


def collect_cases(
    run_dirs: Mapping[str, Path], refs: Mapping[str, Evidence] | None = None
) -> list[FailureCase]:
    """Failure cases of every run, sorted by pipeline (PIPELINE_ORDER) then id."""
    cases: list[FailureCase] = []
    for pipeline in PIPELINE_ORDER:
        run_dir = Path(run_dirs[pipeline])
        records = load_records(run_dir)
        ev = effective_verdicts(run_dir, records)
        faith = faithfulness_by_id(run_dir)
        found = (build_case(pipeline, r, ev, faith, refs) for r in records)
        cases += sorted((c for c in found if c is not None), key=lambda c: c.record.id)
    return cases


def render_csv(cases: list[FailureCase]) -> str:
    """results/failure_labels.csv content (LF line endings)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for c in cases:
        faith = "" if c.faithfulness is None else f"{c.faithfulness:.{SCORE_DIGITS}f}"
        correctness = "" if c.correctness is None else str(c.correctness)
        writer.writerow(
            [
                c.pipeline,
                c.record.id,
                c.record.category,
                correctness,
                c.auto_label,
                c.auto_reason,
                c.proposed_label,
                c.final_label,
                c.note,
                faith,
            ]
        )
    return buffer.getvalue()


def _count_table(cases: list[FailureCase]) -> list[str]:
    """Counts of automatic and proposed labels per pipeline."""
    rows: dict[str, dict[str, int]] = {}
    for c in cases:
        key = c.auto_label if c.auto_label != NEEDS_LABEL else f"{c.proposed_label} (proposed)"
        rows.setdefault(key, dict.fromkeys(PIPELINE_ORDER, 0))[c.pipeline] += 1
    order = [lab for lab, _ in AUTO_LABELS] + [f"{lab} (proposed)" for lab, _ in PROPOSAL_LABELS]
    lines = ["| Label | " + " | ".join(PIPELINE_ORDER) + " | total |", "|---|---|---|---|---|"]
    for label in (k for k in order if k in rows):
        counts = [rows[label][p] for p in PIPELINE_ORDER]
        lines.append(f"| {label} | " + " | ".join(map(str, counts)) + f" | {sum(counts)} |")
    totals = [sum(1 for c in cases if c.pipeline == p) for p in PIPELINE_ORDER]
    return lines + ["| all failed items | " + " | ".join(map(str, totals)) + f" | {sum(totals)} |"]


def _header(cases: list[FailureCase]) -> list[str]:
    """Instructions, label definitions and the count table."""
    lines = [
        "# Failure review",
        "",
        "Generated by `scripts/failure_breakdown.py` from the committed runs. Every failed "
        "item of every pipeline has one section below.",
        "",
        "## How to answer",
        "",
        'Reply with one line per row you want to change, in the form "<pipeline> <id> <label>", '
        'for example "corrective q034 incomplete_answer", then the line "all other rows OK".',
        "",
        "## Allowed labels",
        "",
    ]
    lines += [f"- `{label}`: {text}" for label, text in AUTO_LABELS + PROPOSAL_LABELS]
    lines += ["", "## Counts", ""] + _count_table(cases) + [""]
    return lines


def _sources(case: FailureCase) -> str:
    """Cited sources as 'title > heading' lines."""
    result = case.record.result
    by_id = {c.chunk.chunk_id: c.chunk for c in result.contexts}
    out = []
    for cite in result.answer.citations:
        chunk = by_id.get(cite.chunk_id)
        text = f"{chunk.title} > {' > '.join(chunk.heading_path)}" if chunk else cite.url
        out.append(f"- {text.rstrip(' >')} ({cite.url})")
    return "\n".join(out) or "- none"


def _section(case: FailureCase) -> list[str]:
    """One review section."""
    rec, result = case.record, case.record.result
    answer = result.answer.text
    shown = answer if len(answer) <= ANSWER_CHARS else answer[:ANSWER_CHARS] + " [cut]"
    decisions = [f"- {e.node}: {e.message}" for e in result.trace if e.type == "decision"]
    v = case.verdict
    judge = (
        f"correctness {v.correctness}, citation_support {v.citation_support}. {v.rationale}"
        if v
        else "not judged (abstained or unanswerable)"
    )
    label = (
        case.auto_label if case.auto_label != NEEDS_LABEL else f"{case.proposed_label} (proposed)"
    )
    evidence = case.auto_reason or case.note
    faith = "n/a" if case.faithfulness is None else f"{case.faithfulness:.{SCORE_DIGITS}f}"
    return [
        f"## {case.pipeline} {rec.id} ({rec.category}, correctness "
        f"{'n/a' if case.correctness is None else case.correctness})",
        "",
        f"**Question:** {rec.question}",
        "",
        f"**Reference answer:** {rec.reference_answer or 'none (unanswerable)'}",
        "",
        "**Answer (first 600 characters):**",
        "",
        "> " + shown.replace("\n", "\n> "),
        "",
        "**Cited sources:**",
        "",
        _sources(case),
        "",
        "**Trace decisions:**",
        "",
        *(decisions or ["- none"]),
        "",
        f"**Judge:** {judge}",
        "",
        f"**RAGAS faithfulness:** {faith}",
        "",
        f"**Label:** `{label}`. Evidence: {evidence}",
        "",
    ]


def render_review(cases: list[FailureCase]) -> str:
    """results/failure_review.md content."""
    lines = _header(cases)
    for case in cases:
        lines += _section(case)
    return "\n".join(lines).rstrip("\n") + "\n"


def write_outputs(cases: list[FailureCase], results_dir: Path) -> tuple[Path, Path]:
    """Write failure_labels.csv and failure_review.md into results_dir."""
    csv_path, md_path = results_dir / "failure_labels.csv", results_dir / "failure_review.md"
    write_text(csv_path, render_csv(cases))
    write_text(md_path, render_review(cases))
    return csv_path, md_path
