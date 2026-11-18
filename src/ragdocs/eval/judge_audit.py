"""Hand audit of the judge on 10 stratified items plus low-scored items (D9).

write_audit picks judged items per category with a fixed seed, then adds every other
judged item whose judge correctness is below a threshold (stratification by judge
score, not a redraw), and writes results/judge_audit.md with a table whose last three
columns the human fills in. score_audit compares the human columns with the run's
current effective verdicts, so after a re-judge the same human labels score the new
verdicts.
"""

import math
import random
from dataclasses import dataclass
from pathlib import Path

from ragdocs.eval.judge import cited_flags, load_records
from ragdocs.eval.scoring import EffectiveVerdicts, effective_verdicts
from ragdocs.io_utils import read_text, write_text
from ragdocs.schemas import EvalRecord

TABLE_HEADER = (
    "| # | id | category | selection | judge correctness | judge citation_support "
    "| human correctness (0/1/2) | human citation_support (0/1) | faithful (yes/no) |"
)
N_COLUMNS = 9


def select_audit_items(
    records: list[EvalRecord], ev: EffectiveVerdicts, seed: int, strata: dict[str, int]
) -> list[EvalRecord]:
    """Pick judged items per category with one seeded RNG, strata in the given order."""
    rng = random.Random(seed)
    by_id = {r.id: r for r in records}
    picked: list[EvalRecord] = []
    for category, k in strata.items():
        pool = sorted(
            r.id
            for r in records
            if r.category == category and r.judge_eligible and r.id in ev.verdicts
        )
        if len(pool) < k:
            raise ValueError(f"Only {len(pool)} judged {category} items; audit needs {k}")
        picked += [by_id[i] for i in sorted(rng.sample(pool, k))]
    return picked


def select_low_score_items(
    records: list[EvalRecord], ev: EffectiveVerdicts, exclude: set[str], below: int
) -> list[EvalRecord]:
    """Judged items with judge correctness below `below` not already in `exclude`, by id."""
    return sorted(
        (
            r
            for r in records
            if r.id in ev.verdicts and r.id not in exclude and ev.verdicts[r.id].correctness < below
        ),
        key=lambda r: r.id,
    )


def _item_section(n: int, r: EvalRecord, ev: EffectiveVerdicts, selection: str) -> list[str]:
    """Markdown details for one audited item."""
    v = ev.verdicts[r.id]
    lines = [f"## {n}. {r.id} ({r.category}; {selection})", "", f"**Question:** {r.question}", ""]
    lines += [f"**Reference answer:** {r.reference_answer}", ""]
    lines += [f"**must_mention:** {', '.join(r.must_mention)}", ""]
    lines += ["**Answer:**", "", r.result.answer.text, "", "**Excerpts (context order):**", ""]
    for idx, (rc, text, cited) in enumerate(
        zip(r.result.contexts, r.context_texts, cited_flags(r), strict=True)
    ):
        flag = "CITED" if cited else "NOT CITED"
        header = " > ".join([rc.chunk.title, *rc.chunk.heading_path])
        lines += [f"[{idx + 1}] {flag} {header} ({rc.chunk.url})", "", "```text", text, "```", ""]
    lines += [
        f"**Judge verdict:** correctness={v.correctness}, citation_support={v.citation_support}",
        "",
        f"**Judge rationale:** {v.rationale}",
        "",
    ]
    return lines


@dataclass
class AuditSelection:
    """Seeded draw plus items added by judge score."""

    seed: int
    drawn: list[EvalRecord]
    added: list[EvalRecord]
    add_below: int

    def rows(self) -> list[tuple[EvalRecord, str]]:
        """Items in table order with their selection label."""
        added_label = f"added: judge score < {self.add_below}"
        return [(r, f"seed {self.seed}") for r in self.drawn] + [
            (r, added_label) for r in self.added
        ]


def render_audit(run_dir: Path, sel: AuditSelection, ev: EffectiveVerdicts) -> str:
    """Return judge_audit.md content with empty human columns."""
    lines = [
        "# Judge audit",
        "",
        f"Run: {Path(run_dir).as_posix()}",
        f"Judge: {ev.judge_model}, prompt version {ev.prompt_version} ({ev.source})",
        "",
        f"Selection: {len(sel.drawn)} items drawn per category with seed {sel.seed}, plus every",
        f"other judged item with judge correctness below {sel.add_below} (stratification by",
        "judge score, not a redraw), flagged in the selection column.",
        "",
        "Fill the three human columns. correctness: 2 = agrees with the reference on every",
        "key fact with the right API names; 1 = partly correct or incomplete, nothing",
        "contradicts the reference; 0 = wrong, contradicts the reference, or outdated or",
        "invented API. citation_support: 1 = every CITED excerpt supports a claim and no",
        "central claim lacks a CITED excerpt. faithful: every claim is supported by the",
        "excerpts (used in M09 to sanity-check RAGAS faithfulness).",
        "",
        TABLE_HEADER,
        "|---" * N_COLUMNS + "|",
    ]
    for n, (r, label) in enumerate(sel.rows(), start=1):
        v = ev.verdicts[r.id]
        lines.append(
            f"| {n} | {r.id} | {r.category} | {label} | {v.correctness} "
            f"| {v.citation_support} |  |  |  |"
        )
    lines.append("")
    for n, (r, label) in enumerate(sel.rows(), start=1):
        lines += _item_section(n, r, ev, label)
    return "\n".join(lines).rstrip() + "\n"


@dataclass
class HumanLabel:
    """One filled row of the audit table."""

    correctness: int | None
    citation_support: int | None
    faithful: str | None


def _cell_int(cell: str) -> int | None:
    return int(cell) if cell.strip().isdigit() else None


def parse_audit_table(markdown: str) -> dict[str, HumanLabel]:
    """Read the human columns of the audit table, keyed by item id."""
    labels: dict[str, HumanLabel] = {}
    in_table = False
    for line in markdown.splitlines():
        if line.strip() == TABLE_HEADER:
            in_table = True
            continue
        if not in_table or line.startswith("|---"):
            continue
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != N_COLUMNS:
            continue
        faithful = cells[8].lower() or None
        labels[cells[1]] = HumanLabel(_cell_int(cells[6]), _cell_int(cells[7]), faithful)
    return labels


def has_human_labels(path: Path) -> bool:
    """True if an existing audit file has any human column filled."""
    if not path.is_file():
        return False
    labels = parse_audit_table(read_text(path))
    return any(
        lab.correctness is not None or lab.citation_support is not None or lab.faithful
        for lab in labels.values()
    )


def write_audit(
    run_dir: Path,
    out_path: Path,
    seed: int,
    strata: dict[str, int],
    force: bool = False,
    add_below: int = 0,
) -> AuditSelection:
    """Write the audit file and return the selection; never overwrites human labels.

    add_below = 0 adds nothing (correctness is never below 0).
    """
    if has_human_labels(out_path) and not force:
        raise FileExistsError(f"{out_path} already has human labels; use --force to overwrite")
    records = load_records(run_dir)
    ev = effective_verdicts(run_dir, records)
    drawn = select_audit_items(records, ev, seed, strata)
    added = select_low_score_items(records, ev, {r.id for r in drawn}, add_below)
    sel = AuditSelection(seed, drawn, added, add_below)
    write_text(out_path, render_audit(run_dir, sel, ev))
    return sel


@dataclass
class AuditScore:
    """Agreement between human labels and the effective judge verdicts."""

    n: int
    correctness_agree: int
    citation_agree: int
    unlabelled: list[str]
    disagreements: list[str]

    def needed(self, rate: float) -> int:
        """Agreements needed on each column for the gate: ceil(rate x n)."""
        return math.ceil(round(rate * self.n, 9))

    def passes(self, rate: float) -> bool:
        """True when both columns reach the gate."""
        need = self.needed(rate)
        return self.correctness_agree >= need and self.citation_agree >= need


def score_audit(run_dir: Path, audit_path: Path) -> AuditScore:
    """Compare human labels in the audit file with the run's effective verdicts."""
    labels = parse_audit_table(read_text(audit_path))
    ev = effective_verdicts(run_dir, load_records(run_dir))
    c_agree = s_agree = 0
    unlabelled: list[str] = []
    disagreements: list[str] = []
    for item_id, lab in labels.items():
        v = ev.verdicts[item_id]
        if lab.correctness is None or lab.citation_support is None:
            unlabelled.append(item_id)
            continue
        c_agree += int(lab.correctness == v.correctness)
        s_agree += int(lab.citation_support == v.citation_support)
        if lab.correctness != v.correctness or lab.citation_support != v.citation_support:
            disagreements.append(
                f"{item_id}: correctness judge {v.correctness} / human {lab.correctness}; "
                f"citation_support judge {v.citation_support} / human {lab.citation_support}"
            )
    return AuditScore(len(labels), c_agree, s_agree, unlabelled, disagreements)
