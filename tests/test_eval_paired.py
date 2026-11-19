"""Tests for the RAGAS report rows and the Paired comparison (M09, D19 noise rule)."""

import shutil
from pathlib import Path

import pytest
from eval_fakes import FakeJudgeLLM, FakePipeline
from test_eval_runner import _judge, _run

from ragdocs.eval.compare import NO_DIFFERENCE, noise_verdict, paired_compare, render_comparison
from ragdocs.eval.report import render_markdown, summarize
from ragdocs.io_utils import write_json, write_jsonl

METRICS = ("faithfulness", "response_relevancy", "context_precision", "context_recall")


@pytest.fixture
def judged_run(tmp_path: Path) -> Path:
    _run(tmp_path, FakePipeline())
    _judge(tmp_path, FakeJudgeLLM())
    return tmp_path / "run"


def _write_ragas(run_dir: Path, values: dict[str, float | None]) -> None:
    """ragas_scores.jsonl with one value per answerable item for every metric, and a summary."""
    rows = [
        {"id": i, "category": "single", **{m: v for m in METRICS}, "errors": {}}
        for i, v in values.items()
    ]
    write_jsonl(run_dir / "ragas_scores.jsonl", rows)
    scored = [v for v in values.values() if v is not None]
    stats = {
        "mean": sum(scored) / len(scored),
        "n_eligible": len(values),
        "n_scored": len(scored),
        "n_errored": len(values) - len(scored),
    }
    write_json(
        run_dir / "ragas_summary.json",
        {
            "metrics": {m: stats for m in METRICS},
            "per_category": {
                "single": {m: {"mean": stats["mean"], "n_scored": len(scored)} for m in METRICS}
            },
        },
    )


@pytest.mark.parametrize(
    ("wins", "losses", "verdict"),
    [
        (0, 0, NO_DIFFERENCE),
        (2, 0, NO_DIFFERENCE),
        (3, 0, "better (+3)"),
        (5, 2, "better (+3)"),
        (4, 2, NO_DIFFERENCE),
        (0, 3, "worse (-3)"),
        (1, 4, "worse (-3)"),
    ],
)
def test_noise_verdict(wins: int, losses: int, verdict: str) -> None:
    assert noise_verdict(wins, losses, margin=3) == verdict


def test_paired_arithmetic_on_common_items() -> None:
    base = {"a": 0.5, "b": 0.5, "c": 0.9, "d": 0.1, "e": 0.4, "x": 1.0}
    other = {"a": 0.8, "b": 0.7, "c": 0.6, "d": 0.5, "e": 0.9}
    ids = set(base) & set(other)  # "x" scored in one run only is excluded
    r = paired_compare(base, other, ids, threshold=0.2, margin=3)
    assert r.n == 5
    assert r.base_mean == pytest.approx(0.48)
    assert r.other_mean == pytest.approx(0.7)
    # diffs: +0.3 win, +0.2 not over threshold, -0.3 loss, +0.4 win, +0.5 win
    assert (r.wins, r.losses) == (3, 1)
    assert r.verdict == NO_DIFFERENCE  # 3 - 1 = 2 < 3
    empty = paired_compare(base, other, set(), threshold=0.2, margin=3)
    assert empty.n == 0 and empty.base_mean is None and empty.verdict == NO_DIFFERENCE


def test_report_adds_ragas_rows_only_when_present(judged_run: Path) -> None:
    md = render_markdown(summarize(judged_run))
    assert "RAGAS" not in md
    _write_ragas(judged_run, {"q001": 0.5, "q002": None})
    summary = summarize(judged_run)
    assert summary["overall"]["ragas_faithfulness"] == {"mean": 0.5, "n": 1, "errored": 1}
    md = render_markdown(summary)
    assert "| RAGAS faithfulness (prose-level grounding signal) | 0.500 (1) |" in md
    assert "| RAGAS context_recall (on contexts given to the generator) | 0.500 (1) |" in md
    assert "| RAGAS context_precision (on contexts given to the generator) | 0.500 (1) |" in md


def test_compare_paired_section(judged_run: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    shutil.copytree(judged_run, other)
    _write_ragas(judged_run, {"q001": 0.2, "q002": 0.3})
    _write_ragas(other, {"q001": 0.9, "q002": 0.35})
    md = render_comparison([judged_run, other])
    assert "## Paired" in md and "### other against run" in md
    row = "| RAGAS faithfulness (prose-level grounding signal) | 2 | 0.250 | 0.625 | 1 | 0 |"
    assert row + " no measurable difference |" in md
    # q001 and q002 judged 2, q003 abstained (counts as 0): mean 4/3 over 3 items
    assert "| correctness (0-2; abstained = 0) | 3 | 1.333 | 1.333 | 0 | 0 |" in md
    assert "| RAGAS faithfulness (prose-level grounding signal) | 0.250 (2) | 0.625 (2) |" in md
    single = render_comparison([judged_run])
    assert "## Paired" in single and single.rstrip().endswith("- only one run given")


def test_correctness_verdict_is_primary_and_count_based(judged_run: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    shutil.copytree(judged_run, other)
    md = render_comparison([judged_run, other])
    verdict = md.index("**Correctness verdict (primary): no measurable difference.**")
    assert "0 items better, 0 worse, 3 unchanged, out of 3 answerable items" in md
    assert verdict < md.index("| correctness (0-2; abstained = 0) | 3 |")
    assert "must_mention coverage (soft signal, D15)" in md
