"""Compare run folders side by side (results/summary.md).

Refuses runs that differ in eval_set sha256, index manifest hash, tracing_enabled,
effective judge prompt version or judge model, because their numbers are not
comparable. The Paired section applies the D19 noise rule per metric over the items
scored in every compared run.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ragdocs.config import Settings, get_settings
from ragdocs.eval.judge import load_records
from ragdocs.eval.report import (
    CATEGORIES,
    CONTEXT_LABEL,
    RAGAS_METRICS,
    correctness_of,
    format_cell,
    reclassification_notes,
    rows_for,
    summarize,
)
from ragdocs.eval.scoring import effective_verdicts
from ragdocs.io_utils import read_jsonl

RAGAS_SCORES_FILE = "ragas_scores.jsonl"
NO_DIFFERENCE = "no measurable difference"
# Per-item metrics in the Paired section (all higher is better); label per key.
PAIRED_METRICS: list[tuple[str, str]] = [
    ("correctness", "correctness (0-2; abstained = 0)"),
    ("context_evidence_recall@5", f"context_evidence_recall@5 ({CONTEXT_LABEL})"),
    ("must_mention_coverage", "must_mention coverage (soft signal, D15)"),
    ("faithfulness", "RAGAS faithfulness (prose-level grounding signal)"),
    ("response_relevancy", "RAGAS response_relevancy"),
    ("context_precision", f"RAGAS context_precision ({CONTEXT_LABEL})"),
    ("context_recall", f"RAGAS context_recall ({CONTEXT_LABEL})"),
]


class IncomparableRuns(ValueError):
    """Raised when runs differ in a setting that makes their numbers incomparable."""


GUARDS = (
    ("eval_set sha256", lambda s: s["eval_set_sha256"]),
    ("index manifest hash", lambda s: s["index_manifest_hash"]),
    ("tracing_enabled", lambda s: s["tracing_enabled"]),
    ("effective judge_prompt_version", lambda s: s["judge"]["effective_prompt_version"]),
    ("judge model", lambda s: s["judge"]["judge_model"]),
)


def check_comparable(summaries: list[dict[str, Any]]) -> None:
    """Raise IncomparableRuns naming the first guard field that differs."""
    for label, get in GUARDS:
        values = {str(get(s)) for s in summaries}
        if len(values) > 1:
            detail = ", ".join(f"{s['run']}={get(s)!r}" for s in summaries)
            raise IncomparableRuns(f"Runs differ in {label}: {detail}")


def item_outcomes(run_dir: Path) -> dict[str, tuple[int | None, bool]]:
    """Return {id: (correctness or None, abstained)} using effective verdicts."""
    records = load_records(run_dir)
    ev = effective_verdicts(run_dir, records)
    out: dict[str, tuple[int | None, bool]] = {}
    for r in records:
        corr = correctness_of(r, ev) if r.category != "unanswerable" else None
        out[r.id] = (corr, r.scores.abstained)
    return out


def _direction(old: Any, new: Any, higher_is_better: bool) -> str:
    """Return 'better', 'worse' or 'changed'."""
    if old is None or new is None:
        return "changed"
    better = new > old if higher_is_better else new < old
    return "better" if better else "worse"


def changed_questions(base: Path, other: Path) -> list[str]:
    """List ids whose correctness or abstention outcome changed against base."""
    a, b = item_outcomes(base), item_outcomes(other)
    lines: list[str] = []
    for item_id in sorted(set(a) & set(b)):
        (c0, ab0), (c1, ab1) = a[item_id], b[item_id]
        parts = []
        if c0 != c1:
            parts.append(f"correctness {c0} -> {c1} ({_direction(c0, c1, True)})")
        if ab0 != ab1:
            parts.append(f"abstained {ab0} -> {ab1}")
        if parts:
            lines.append(f"- {item_id}: " + "; ".join(parts))
    return lines


def _table(summaries: list[dict[str, Any]], section: str, cat: str | None) -> list[str]:
    """One Markdown table with one column per run."""
    lines = ["| Field | " + " | ".join(s["run"] for s in summaries) + " |"]
    lines.append("|---|" + "---|" * len(summaries))
    for label, key, kind in rows_for(summaries):
        cells = [
            format_cell(s[section] if cat is None else s[section][cat], key, kind)
            for s in summaries
        ]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


def item_values(run_dir: Path) -> dict[str, dict[str, float]]:
    """Per paired metric: {item id: value}; items without a value are left out."""
    records = load_records(run_dir)
    ev = effective_verdicts(run_dir, records)
    out: dict[str, dict[str, float]] = {key: {} for key, _ in PAIRED_METRICS}
    for r in records:
        if r.category == "unanswerable":
            continue
        values = {
            "correctness": correctness_of(r, ev),
            "context_evidence_recall@5": r.scores.context_evidence_recall_at_5,
            "must_mention_coverage": r.scores.must_mention_coverage,
        }
        for key, v in values.items():
            if v is not None:
                out[key][r.id] = float(v)
    ragas_path = Path(run_dir) / RAGAS_SCORES_FILE
    for row in read_jsonl(ragas_path) if ragas_path.is_file() else []:
        for m in RAGAS_METRICS:
            if row.get(m) is not None:
                out[m][row["id"]] = float(row[m])
    return out


@dataclass(frozen=True)
class PairedResult:
    """One non-first run against the first on one metric, over the common items."""

    n: int
    base_mean: float | None
    other_mean: float | None
    wins: int
    losses: int
    verdict: str


def noise_verdict(wins: int, losses: int, margin: int) -> str:
    """D19: a direction only when wins minus losses (or the reverse) is at least margin."""
    if wins - losses >= margin:
        return f"better (+{wins - losses})"
    if losses - wins >= margin:
        return f"worse (-{losses - wins})"
    return NO_DIFFERENCE


def paired_compare(
    base: dict[str, float],
    other: dict[str, float],
    ids: set[str],
    threshold: float,
    margin: int,
) -> PairedResult:
    """Means over ids and the count of items better or worse by more than threshold."""
    diffs = [other[i] - base[i] for i in sorted(ids)]
    wins = sum(1 for d in diffs if d > threshold)
    losses = sum(1 for d in diffs if d < -threshold)
    n = len(ids)
    return PairedResult(
        n=n,
        base_mean=sum(base[i] for i in ids) / n if n else None,
        other_mean=sum(other[i] for i in ids) / n if n else None,
        wins=wins,
        losses=losses,
        verdict=noise_verdict(wins, losses, margin) if n else NO_DIFFERENCE,
    )


def _fmt(value: float | None) -> str:
    """Three-decimal mean or '-'."""
    return "-" if value is None else f"{value:.3f}"


def correctness_verdict_line(
    base: dict[str, dict[str, float]],
    other: dict[str, dict[str, float]],
    values: list[dict[str, dict[str, float]]],
    threshold: float,
    margin: int,
) -> str:
    """Primary correctness verdict: count of items better and worse (D19 noise rule)."""
    ids = set.intersection(*(set(v["correctness"]) for v in values))
    r = paired_compare(base["correctness"], other["correctness"], ids, threshold, margin)
    return (
        f"**Correctness verdict (primary): {r.verdict}.** {r.wins} items better, "
        f"{r.losses} worse, {r.n - r.wins - r.losses} unchanged, out of {r.n} answerable "
        f"items (a direction needs a net of {margin} items). The correctness row in the "
        "table is supporting detail; must_mention coverage is a soft signal (D15)."
    )


def paired_section(run_dirs: list[Path], settings: Settings) -> list[str]:
    """Markdown 'Paired' section: one table per non-first run against the first."""
    threshold, margin = settings.compare_paired_threshold, settings.compare_noise_margin
    lines = [
        "## Paired",
        "",
        f"Means over items scored in every compared run (n). A paired item is better or "
        f"worse when the difference exceeds {threshold}; the verdict is "
        f'"{NO_DIFFERENCE}" unless wins minus losses is {margin} or more (D19).',
    ]
    if len(run_dirs) < 2:
        return lines + ["", "- only one run given"]
    values = [item_values(d) for d in run_dirs]
    for idx, other in enumerate(run_dirs[1:], start=1):
        lines += ["", f"### {other.name} against {run_dirs[0].name}", ""]
        lines += [correctness_verdict_line(values[0], values[idx], values, threshold, margin), ""]
        lines += ["| Metric | n | first mean | this mean | better | worse | verdict |"]
        lines += ["|---|---|---|---|---|---|---|"]
        for key, label in PAIRED_METRICS:
            ids = set.intersection(*(set(v[key]) for v in values))
            r = paired_compare(values[0][key], values[idx][key], ids, threshold, margin)
            lines.append(
                f"| {label} | {r.n} | {_fmt(r.base_mean)} | {_fmt(r.other_mean)} | "
                f"{r.wins} | {r.losses} | {r.verdict} |"
            )
    return lines


def render_comparison(run_dirs: list[Path], settings: Settings | None = None) -> str:
    """Return the comparison Markdown; raises IncomparableRuns on guard mismatch."""
    settings = settings or get_settings()
    summaries = [summarize(d) for d in run_dirs]
    check_comparable(summaries)
    judge = summaries[0]["judge"]
    lines = ["# Run comparison", ""]
    lines.append(
        f"Judge {judge['judge_model']}, prompt version {judge['effective_prompt_version']}. "
        "Rates are rate (count/n); correctness n = every answerable item."
    )
    lines += ["", "## Overall", ""] + _table(summaries, "overall", None)
    notes = reclassification_notes(summaries)
    lines += ["", *notes] if notes else []
    for cat in CATEGORIES:
        lines += ["", f"## {cat}", ""] + _table(summaries, "per_category", cat)
    lines += ["", f"## Changed questions (against {summaries[0]['run']})", ""]
    for other in run_dirs[1:]:
        changes = changed_questions(run_dirs[0], other)
        lines += [f"### {other.name}", ""] + (changes or ["- none"]) + [""]
    if len(run_dirs) == 1:
        lines.append("- only one run given")
    lines += [""] + paired_section(run_dirs, settings)
    return "\n".join(lines).rstrip() + "\n"
