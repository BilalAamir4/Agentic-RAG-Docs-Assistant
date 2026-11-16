"""Tests for summary arithmetic, effective verdicts, compare_runs and the judge audit."""

import shutil
from pathlib import Path

import pytest
from eval_fakes import FakeClock, FakeJudgeLLM, FakePipeline, make_settings
from test_eval_runner import _judge, _run

from ragdocs.eval.compare import IncomparableRuns, changed_questions, render_comparison
from ragdocs.eval.judge_audit import parse_audit_table, score_audit, write_audit
from ragdocs.eval.report import format_rate, rate, render_markdown, summarize
from ragdocs.io_utils import append_jsonl, read_json, read_text, write_json, write_text
from ragdocs.schemas import JudgeRecord, JudgeVerdict


@pytest.fixture
def judged_run(tmp_path: Path) -> Path:
    """Fake run of 4 items, q001 and q002 judged (2, 1)."""
    _run(tmp_path, FakePipeline())
    _judge(tmp_path, FakeJudgeLLM())
    return tmp_path / "run"


def test_format_rate() -> None:
    assert format_rate(rate(2, 3)) == "0.667 (2/3)"
    assert format_rate(rate(0, 0)) == "-"
    assert format_rate(rate(2.5, 3)) == "0.833 (2.5/3)"


def test_summary_arithmetic(judged_run: Path) -> None:
    s = summarize(judged_run)
    o = s["overall"]
    assert o["answerable_n"] == 3 and o["unanswerable_n"] == 1
    assert o["correct"] == {"count": 2, "n": 3, "rate": 2 / 3}  # false abstention counts as 0
    assert o["correct_or_partial"]["count"] == 2
    assert o["mean_correctness"]["mean"] == pytest.approx(4 / 3)
    assert o["citation_support"] == {"count": 2, "n": 2, "rate": 1.0}
    assert o["context_hit@5"]["count"] == 3
    assert o["context_evidence_recall@5"]["mean"] == pytest.approx((1 + 0.5 + 1) / 3)
    assert o["must_mention_coverage"]["mean"] == pytest.approx(2 / 3)
    assert o["false_abstention"]["count"] == 1
    assert o["hallucinated"]["count"] == 1 and o["abstention_correct"]["count"] == 0
    assert o["latency_ms_p50"] == 250.0 and o["latency_ms_p95"] == pytest.approx(385.0)
    assert o["mean_tokens_per_question"]["mean"] == 1200.0
    assert o["used_web"]["count"] == 0
    assert s["per_category"]["unanswerable"]["hallucinated"]["n"] == 1
    assert s["per_category"]["single"]["correct"] == {"count": 1, "n": 1, "rate": 1.0}
    assert s["judge"]["complete"] is True and s["judge"]["effective_prompt_version"] == 1
    md = render_markdown(s)
    assert "| correct (correctness = 2) | 0.667 (2/3) |" in md
    assert "on contexts given to the generator" in md


def test_summary_flags_incomplete_judging(tmp_path: Path) -> None:
    _run(tmp_path, FakePipeline())
    s = summarize(tmp_path / "run")
    assert s["judge"]["complete"] is False and s["overall"]["judge_missing"] == 2
    assert "WARNING: judging incomplete" in render_markdown(s)


def _write_v2(run_dir: Path, correctness: int) -> None:
    for item_id in ("q001", "q002"):
        rec = JudgeRecord(
            id=item_id,
            verdict=JudgeVerdict(correctness=correctness, citation_support=1, rationale="v2"),
            judge_model="gemini-3.5-flash-lite",
            judge_prompt_version=2,
        )
        append_jsonl(run_dir / "judge_v2.jsonl", rec.model_dump(mode="json"))


def test_highest_judge_file_wins(judged_run: Path) -> None:
    _write_v2(judged_run, correctness=1)
    s = summarize(judged_run)
    assert s["judge"]["effective_prompt_version"] == 2
    assert s["overall"]["correct"]["count"] == 0
    assert s["overall"]["correct_or_partial"]["count"] == 2


def test_extra_score_files_do_not_change_fields(judged_run: Path, tmp_path: Path) -> None:
    extra = tmp_path / "ragas.jsonl"
    append_jsonl(extra, {"id": "q001", "faithfulness": 0.5})
    append_jsonl(extra, {"id": "q002", "faithfulness": None})
    base = summarize(judged_run)
    merged = summarize(judged_run, [extra])
    assert merged["overall"] == base["overall"]
    assert merged["extra"]["ragas"]["faithfulness"] == {"mean": 0.5, "n": 1}


def _copy_run(src: Path, dst: Path, **config_changes: object) -> Path:
    shutil.copytree(src, dst)
    cfg = read_json(dst / "config.json")
    cfg.update(config_changes)
    write_json(dst / "config.json", cfg)
    return dst


def test_compare_refuses_mismatched_hashes(judged_run: Path, tmp_path: Path) -> None:
    other = _copy_run(judged_run, tmp_path / "other", eval_set_sha256="f" * 64)
    with pytest.raises(IncomparableRuns, match="eval_set sha256"):
        render_comparison([judged_run, other])
    other2 = _copy_run(judged_run, tmp_path / "other2", index_manifest_hash="abc")
    with pytest.raises(IncomparableRuns, match="index manifest hash"):
        render_comparison([judged_run, other2])


def test_compare_refuses_mixed_tracing(judged_run: Path, tmp_path: Path) -> None:
    other = _copy_run(judged_run, tmp_path / "other", tracing_enabled=True)
    with pytest.raises(IncomparableRuns, match="tracing_enabled"):
        render_comparison([judged_run, other])


def test_compare_refuses_mixed_judge_version(judged_run: Path, tmp_path: Path) -> None:
    other = _copy_run(judged_run, tmp_path / "other")
    _write_v2(other, correctness=2)
    with pytest.raises(IncomparableRuns, match="judge_prompt_version"):
        render_comparison([judged_run, other])


def test_compare_lists_changed_questions(judged_run: Path, tmp_path: Path) -> None:
    other = _copy_run(judged_run, tmp_path / "other")
    (other / "judge_v1.jsonl").unlink()
    _judge_with(other, tmp_path, JudgeVerdict(correctness=1, citation_support=0, rationale="x"))
    changes = changed_questions(judged_run, other)
    assert changes == [
        "- q001: correctness 2 -> 1 (worse)",
        "- q002: correctness 2 -> 1 (worse)",
    ]
    md = render_comparison([judged_run, other])
    assert "## Changed questions (against run)" in md and "## multi" in md


def _judge_with(run_dir: Path, tmp_path: Path, verdict: JudgeVerdict) -> None:
    from test_eval_runner import _DictCache

    from ragdocs.eval.judge_run import run_judge
    from ragdocs.eval.throttle import RollingBudget

    clock = FakeClock()
    run_judge(
        run_dir,
        settings=make_settings(tmp_path / "s2"),
        llm=FakeJudgeLLM(verdict),
        budget=RollingBudget("j", 250000, 15, 500, clock=clock, sleep=clock.sleep),
        cache=_DictCache(),
        out=lambda m: None,
    )


def test_judge_audit_write_parse_score(judged_run: Path, tmp_path: Path) -> None:
    audit = tmp_path / "judge_audit.md"
    ids = write_audit(judged_run, audit, seed=21, strata={"single": 1, "multi": 1})
    assert ids == ["q001", "q002"]
    text = read_text(audit)
    assert "| 1 | q001 | single | 2 | 1 |  |  |  |" in text
    assert "[2] CITED Title 2 > H2" in text
    filled = text.replace(
        "| 1 | q001 | single | 2 | 1 |  |  |  |", "| 1 | q001 | single | 2 | 1 | 2 | 1 | yes |"
    )
    filled = filled.replace(
        "| 2 | q002 | multi | 2 | 1 |  |  |  |", "| 2 | q002 | multi | 2 | 1 | 1 | 1 | no |"
    )
    write_text(audit, filled)
    labels = parse_audit_table(read_text(audit))
    assert labels["q002"].correctness == 1 and labels["q002"].faithful == "no"
    score = score_audit(judged_run, audit)
    assert (score.n, score.correctness_agree, score.citation_agree) == (2, 1, 2)
    assert len(score.disagreements) == 1
    with pytest.raises(FileExistsError):
        write_audit(judged_run, audit, seed=21, strata={"single": 1, "multi": 1})


def test_judge_audit_needs_enough_items(judged_run: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="single"):
        write_audit(judged_run, tmp_path / "a.md", seed=21, strata={"single": 6})
