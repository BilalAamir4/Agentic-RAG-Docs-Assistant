"""Compare run folders side by side (results/summary.md).

Refuses runs that differ in eval_set sha256, index manifest hash, tracing_enabled,
effective judge prompt version or judge model, because their numbers are not
comparable.
"""

from pathlib import Path
from typing import Any

from ragdocs.eval.judge import load_records
from ragdocs.eval.report import CATEGORIES, SUMMARY_ROWS, correctness_of, format_cell, summarize
from ragdocs.eval.scoring import effective_verdicts


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
    for label, key, kind in SUMMARY_ROWS:
        cells = [
            format_cell(s[section] if cat is None else s[section][cat], key, kind)
            for s in summaries
        ]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


def render_comparison(run_dirs: list[Path]) -> str:
    """Return the comparison Markdown; raises IncomparableRuns on guard mismatch."""
    summaries = [summarize(d) for d in run_dirs]
    check_comparable(summaries)
    judge = summaries[0]["judge"]
    lines = ["# Run comparison", ""]
    lines.append(
        f"Judge {judge['judge_model']}, prompt version {judge['effective_prompt_version']}. "
        "Rates are rate (count/n); correctness n = every answerable item."
    )
    lines += ["", "## Overall", ""] + _table(summaries, "overall", None)
    for cat in CATEGORIES:
        lines += ["", f"## {cat}", ""] + _table(summaries, "per_category", cat)
    lines += ["", f"## Changed questions (against {summaries[0]['run']})", ""]
    for other in run_dirs[1:]:
        changes = changed_questions(run_dirs[0], other)
        lines += [f"### {other.name}", ""] + (changes or ["- none"]) + [""]
    if len(run_dirs) == 1:
        lines.append("- only one run given")
    return "\n".join(lines).rstrip() + "\n"
