"""Failure labels: each rule, its precedence, the CSV layout and determinism (M15)."""

from pathlib import Path

from eval_fakes import make_chunk

from ragdocs.eval.failure_review import (
    CSV_COLUMNS,
    NEEDS_LABEL,
    FailureCase,
    auto_label,
    build_case,
    collect_cases,
    render_csv,
    render_review,
    write_outputs,
)
from ragdocs.eval.scoring import EffectiveVerdicts
from ragdocs.io_utils import read_text, write_jsonl
from ragdocs.schemas import (
    Answer,
    EvalRecord,
    Evidence,
    ItemScores,
    JudgeVerdict,
    PipelineResult,
    TokenUsageRecord,
    TraceEvent,
)

GOLD = Evidence(doc_path="gold.mdx", anchor="g")
REFS = {"c1": Evidence(doc_path="other.mdx", anchor="o"), "gold": GOLD}


def _event(type_: str, node: str, **data: object) -> TraceEvent:
    return TraceEvent(type=type_, node=node, message=f"{node} message", data=dict(data), t_ms=0)


def _record(
    *,
    pipeline: str = "corrective",
    category: str = "single",
    first_hit: bool = True,
    context_hit: float = 1.0,
    abstained: bool = False,
    hallucinated: bool | None = None,
    used_web: bool = False,
    extra_trace: list[TraceEvent] | None = None,
    diagnostics: dict | None = None,
    qid: str = "q001",
) -> EvalRecord:
    chunk_id = "gold" if first_hit else "c1"
    trace = [_event("retrieval", "retrieve", chunks=[{"chunk_id": chunk_id, "url": "u"}])]
    result = PipelineResult(
        question="Q?",
        pipeline=pipeline,
        answer=Answer(text="A", citations=[], abstained=abstained),
        contexts=[make_chunk(1)],
        trace=trace + (extra_trace or []),
        llm_calls=1,
        latency_ms=1,
        used_web=used_web,
        diagnostics=diagnostics or {},
    )
    scores = ItemScores(
        abstained=abstained,
        hallucinated=hallucinated,
        context_hit_at_5=context_hit,
        llm_calls=1,
        latency_ms=1,
        used_web=used_web,
        tokens_in=1,
        tokens_out=1,
    )
    return EvalRecord(
        id=qid,
        category=category,
        question="Q?",
        reference_answer=None if category == "unanswerable" else "Ref.",
        evidence=[] if category == "unanswerable" else [GOLD],
        must_mention=[],
        result=result,
        context_texts=[],
        usage=TokenUsageRecord(),
        langsmith_run_id=None,
        scores=scores,
        judge_eligible=True,
    )


def _label(record: EvalRecord) -> str:
    return auto_label(record, 0, REFS)[0]


def _ev(record: EvalRecord, correctness: int, rationale: str = "ok") -> EffectiveVerdicts:
    verdict = JudgeVerdict(correctness=correctness, citation_support=1, rationale=rationale)
    return EffectiveVerdicts(
        verdicts={record.id: verdict}, prompt_version=2, judge_model="m", source="judge_v2.jsonl"
    )


def test_router_out_of_scope_comes_first() -> None:
    rec = _record(
        pipeline="self_rag",
        first_hit=False,
        abstained=True,
        used_web=True,
        extra_trace=[
            _event("decision", "out_of_scope"),
            _event("decision", "x", grading_failed=True),
        ],
    )
    assert _label(rec) == "router_out_of_scope"


def test_structured_output_failure_beats_retrieval_miss() -> None:
    rec = _record(first_hit=False, diagnostics={"fallbacks": ["verify_failed"]})
    assert _label(rec) == "structured_output_failure"
    grading = _record(extra_trace=[_event("decision", "grade_documents", grading_failed=True)])
    assert _label(grading) == "structured_output_failure"
    counter = _record(diagnostics={"invalid_grades": 2})
    assert _label(counter) == "structured_output_failure"
    zero = _record(diagnostics={"invalid_grades": 0})
    assert _label(zero) == NEEDS_LABEL


def test_retrieval_miss_beats_false_abstention_and_web() -> None:
    rec = _record(first_hit=False, abstained=True, used_web=True)
    label, reason = auto_label(rec, 0, REFS)
    assert label == "retrieval_miss"
    assert reason == "gold anchor gold.mdx#g not in first top 5"


def test_grading_drop_only_for_filtering_pipelines() -> None:
    assert _label(_record(context_hit=0.0, abstained=True)) == "grading_drop"
    baseline = _record(pipeline="baseline", context_hit=0.0, abstained=True)
    # The baseline's contexts are its first retrieval (D22), so a context miss is a retrieval miss.
    assert _label(baseline) == "retrieval_miss"


def test_false_abstention_then_web_then_needs_label() -> None:
    assert _label(_record(abstained=True, used_web=True)) == "false_abstention"
    assert _label(_record(used_web=True)) == "web_used_failure"
    assert _label(_record()) == NEEDS_LABEL


def test_hallucinated_unanswerable() -> None:
    rec = _record(category="unanswerable", hallucinated=True, first_hit=False)
    assert auto_label(rec, None, REFS)[0] == "hallucinated_unanswerable"
    ok = _record(category="unanswerable", hallucinated=False, abstained=True)
    assert build_case("corrective", ok, _ev(ok, 2), {}, REFS) is None


def test_passing_item_is_not_a_case() -> None:
    rec = _record()
    assert build_case("corrective", rec, _ev(rec, 2), {}, REFS) is None


def test_final_label_prefilled_for_auto_only() -> None:
    auto = _record(abstained=True, qid="q002")
    case = build_case("corrective", auto, _ev(auto, 2), {}, REFS)
    assert case is not None
    assert case.final_label == "false_abstention" and case.proposed_label == ""
    other = _record(qid="q003")
    proposed = build_case(
        "corrective", other, _ev(other, 1, "It invents an API."), {"q003": 0.5}, REFS
    )
    assert proposed is not None
    assert proposed.auto_label == NEEDS_LABEL and proposed.final_label == ""
    assert proposed.proposed_label == "unfaithful_generation"
    assert "RAGAS faithfulness 0.500 (low)" in proposed.note


def test_proposals() -> None:
    def proposal(rationale: str, trace: list[TraceEvent] | None = None) -> str:
        rec = _record(extra_trace=trace)
        case = build_case("corrective", rec, _ev(rec, 1, rationale), {}, REFS)
        assert case is not None
        return case.proposed_label

    assert proposal("fine", [_event("decision", "rewrite_query")]) == "rewrite_drift"
    assert proposal("fine", [_event("decision", "regenerate")]) == "verifier_false_alarm"
    assert proposal("It omits the reducer.") == "incomplete_answer"
    assert proposal("Looks different from the reference.") == "judge_disagreement"


def _cases() -> list[FailureCase]:
    out = []
    for pipeline, qid in (("baseline", "q003"), ("baseline", "q020"), ("self_rag", "q009")):
        rec = _record(pipeline=pipeline, abstained=True, qid=qid)
        case = build_case(pipeline, rec, _ev(rec, 2), {}, REFS)
        assert case is not None
        out.append(case)
    return out


def test_csv_columns_and_determinism() -> None:
    first, second = render_csv(_cases()), render_csv(_cases())
    assert first == second
    assert "\r" not in first
    assert first.splitlines()[0] == ",".join(CSV_COLUMNS)
    assert len(first.splitlines()) == 4


def test_review_header_and_one_section_per_row() -> None:
    cases = _cases()
    text = render_review(cases)
    assert text == render_review(cases)
    assert "all other rows OK" in text
    assert "## How to answer" in text and "## Allowed labels" in text and "## Counts" in text
    assert sum(1 for line in text.splitlines() if line.startswith("## baseline q")) == 2
    assert "## self_rag q009" in text


def test_collect_sorts_by_pipeline_then_id_and_writes_files(tmp_path: Path) -> None:
    dirs = {}
    for pipeline, ids in (
        ("self_rag", ["q009"]),
        ("baseline", ["q020", "q003"]),
        ("corrective", []),
    ):
        run = tmp_path / pipeline
        run.mkdir()
        rows = [
            _record(pipeline=pipeline, abstained=True, qid=i).model_dump(by_alias=True, mode="json")
            for i in ids
        ]
        write_jsonl(run / "per_question.jsonl", rows)
        dirs[pipeline] = run
    cases = collect_cases(dirs, REFS)
    assert [(c.pipeline, c.record.id) for c in cases] == [
        ("baseline", "q003"),
        ("baseline", "q020"),
        ("self_rag", "q009"),
    ]
    csv_path, md_path = write_outputs(cases, tmp_path)
    assert read_text(csv_path) == render_csv(cases)
    assert read_text(md_path) == render_review(cases)
