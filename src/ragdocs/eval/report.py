"""Run summaries (summary.json, summary.md) computed from a run folder.

Verdicts come from the highest judge_v<N>.jsonl present (else per_question.jsonl),
see ragdocs.eval.scoring.effective_verdicts. Correctness fields use n = every
answerable item and count a false abstention as correctness 0, so a pipeline that
abstains more cannot look more accurate. When the run folder has ragas_summary.json
(M09), the four RAGAS metrics are added as "mean (n)" rows; n is the number of
eligible items scored (errored and NaN items excluded).

first_retrieval_hit@5 (M10, D22) is computed from each item's stored trace, not from
per_question scores: see first_retrieval_hit_at_5.
"""

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ragdocs.config import get_settings
from ragdocs.docs_urls import CHUNK_META_FILE, url_to_doc_ref
from ragdocs.eval.failures import (
    KIND_FIELDS,
    count_kinds,
    item_kinds,
    load_overrides,
    overrides_for_run,
    overrides_path,
)
from ragdocs.eval.judge import load_records
from ragdocs.eval.metrics import hit_at_k
from ragdocs.eval.scoring import EffectiveVerdicts, effective_verdicts
from ragdocs.io_utils import read_json, read_jsonl, write_json, write_text
from ragdocs.schemas import ErrorReclassification, EvalRecord, Evidence, PipelineResult

CATEGORIES = ("single", "multi", "version", "unanswerable")
CONTEXT_LABEL = "on contexts given to the generator"
RAGAS_SUMMARY_FILE = "ragas_summary.json"
RAGAS_METRICS = ("faithfulness", "response_relevancy", "context_precision", "context_recall")
# Row label, key, formatter kind for the RAGAS rows (D22 label on the context metrics).
RAGAS_ROWS: list[tuple[str, str, str]] = [
    ("RAGAS faithfulness (prose-level grounding signal)", "ragas_faithfulness", "ragas"),
    ("RAGAS response_relevancy", "ragas_response_relevancy", "ragas"),
    (f"RAGAS context_precision ({CONTEXT_LABEL})", "ragas_context_precision", "ragas"),
    (f"RAGAS context_recall ({CONTEXT_LABEL})", "ragas_context_recall", "ragas"),
]


FIRST_RETRIEVAL_K = 5
# Self-RAG fallback types in diagnostics["fallbacks"] (M11, D26), in display order.
FALLBACK_TYPES = ("decide_failed", "verify_failed", "regenerate_failed")
RECLASSIFICATIONS_LABEL = "results/error_reclassifications.json"
# Pipelines whose generator contexts are exactly the top chunks of their first (and
# only) retrieval, so first_retrieval_hit@5 equals context_hit@5 by construction (D22).
# The baseline's stored retrieval event lists url but no chunk_id (M10 S1 check 1h;
# all 50 baseline items: one retrieval event whose 5 URLs equal the 5 context URLs in
# order), so its value is computed from its contexts.
CONTEXTS_ARE_FIRST_RETRIEVAL = frozenset({"baseline"})


@lru_cache
def chunk_refs(index_dir: Path | None = None) -> dict[str, Evidence]:
    """{chunk_id: (doc_path, anchor)} from <index_dir>/chunk_meta.jsonl (default Settings)."""
    path = Path(index_dir or get_settings().index_dir) / CHUNK_META_FILE
    return {
        row["chunk_id"]: Evidence(doc_path=row["doc_path"], anchor=row["anchor"])
        for row in read_jsonl(path)
    }


def first_retrieval_refs(
    result: PipelineResult, refs: Mapping[str, Evidence] | None = None
) -> list[Evidence | None] | None:
    """(doc_path, anchor) of the top FIRST_RETRIEVAL_K chunks of the first retrieval event.

    Each chunk resolves by chunk_id in refs (default: the index's chunk_meta.jsonl),
    else by docs_urls.url_to_doc_ref(url); None marks a chunk that resolves to nothing.
    Returns None when the trace has no retrieval event.
    """
    event = next((e for e in result.trace if e.type == "retrieval"), None)
    if event is None:
        return None
    out: list[Evidence | None] = []
    for chunk in (event.data.get("chunks") or [])[:FIRST_RETRIEVAL_K]:
        chunk_id, url = chunk.get("chunk_id"), chunk.get("url")
        ref = None
        if chunk_id:
            ref = (chunk_refs() if refs is None else refs).get(chunk_id)
        if ref is None and url:
            ref = url_to_doc_ref(url)
        out.append(ref)
    return out


def first_retrieval_hit_at_5(
    record: EvalRecord, refs: Mapping[str, Evidence] | None = None
) -> float:
    """1.0 when a top-5 chunk of the item's first retrieval matches its gold evidence.

    Like-for-like retrieval comparison across pipelines (D22). No retrieval event
    counts as a miss. CONTEXTS_ARE_FIRST_RETRIEVAL pipelines use their contexts.
    """
    result = record.result
    if result.pipeline in CONTEXTS_ARE_FIRST_RETRIEVAL:
        return hit_at_k(result.contexts, record.evidence, FIRST_RETRIEVAL_K)
    resolved = first_retrieval_refs(result, refs)
    if resolved is None:
        return 0.0
    matched = [r for r in resolved if r is not None]
    return hit_at_k(matched, record.evidence, FIRST_RETRIEVAL_K)


def rate(count: int | float, n: int) -> dict[str, Any]:
    """Return {"count", "n", "rate"}; rate is None when n is 0."""
    return {"count": count, "n": n, "rate": (count / n) if n else None}


def mean(values: Sequence[float]) -> dict[str, Any]:
    """Return {"mean", "n"}; mean is None for an empty sequence."""
    return {"mean": float(np.mean(values)) if values else None, "n": len(values)}


def format_rate(r: dict[str, Any]) -> str:
    """Format a rate dict as 'rate (count/n)', or '-' when n is 0."""
    if not r["n"]:
        return "-"
    count = r["count"]
    count_s = str(int(count)) if float(count).is_integer() else f"{count:.1f}"
    return f"{r['rate']:.3f} ({count_s}/{r['n']})"


def format_mean(m: dict[str, Any], unit: str = "") -> str:
    """Format a mean dict as 'mean (n=N)', or '-' when empty."""
    if m["mean"] is None:
        return "-"
    return f"{m['mean']:.3f}{unit} (n={m['n']})"


def correctness_of(record: EvalRecord, ev: EffectiveVerdicts) -> int | None:
    """Correctness for an answerable item: 0 if abstained, else the verdict (None if unjudged)."""
    if record.scores.abstained:
        return 0
    verdict = ev.verdicts.get(record.id)
    return verdict.correctness if verdict is not None else None


def _answer_metrics(answerable: list[EvalRecord], ev: EffectiveVerdicts) -> dict[str, Any]:
    """Correctness, citation, context and abstention metrics over answerable items."""
    n = len(answerable)
    corr = [correctness_of(r, ev) for r in answerable]
    judged = [ev.verdicts[r.id] for r in answerable if r.judge_eligible and r.id in ev.verdicts]
    hits = [r.scores.context_hit_at_5 or 0.0 for r in answerable]
    first_hits = [first_retrieval_hit_at_5(r) for r in answerable]
    recall = [r.scores.context_evidence_recall_at_5 or 0.0 for r in answerable]
    coverage = [
        r.scores.must_mention_coverage
        for r in answerable
        if r.scores.must_mention_coverage is not None
    ]
    return {
        "answerable_n": n,
        "judge_missing": sum(1 for c in corr if c is None),
        "correct": rate(sum(1 for c in corr if c == 2), n),
        "correct_or_partial": rate(sum(1 for c in corr if c is not None and c >= 1), n),
        "mean_correctness": {"mean": (sum(c or 0 for c in corr) / n) if n else None, "n": n},
        "citation_support": rate(sum(v.citation_support for v in judged), len(judged)),
        "first_retrieval_hit@5": rate(sum(first_hits), n),
        "context_hit@5": rate(sum(hits), n),
        "context_evidence_recall@5": mean(recall),
        "must_mention_coverage": mean(coverage),
        "false_abstention": rate(sum(1 for r in answerable if r.scores.abstained), n),
    }


def _metrics(
    records: list[EvalRecord],
    ev: EffectiveVerdicts,
    kinds: Mapping[str, list[str]] | None = None,
) -> dict[str, Any]:
    """All summary fields over one subset of records.

    kinds maps item id to the kind of each failed attempt (record_kinds); by default the
    kinds come from the stored attempts without overrides.
    """
    answerable = [r for r in records if r.category != "unanswerable"]
    unanswerable = [r for r in records if r.category == "unanswerable"]
    latencies = [r.scores.latency_ms for r in records]
    tokens = [r.scores.tokens_in + r.scores.tokens_out for r in records]
    out = {"n": len(records), **_answer_metrics(answerable, ev)}
    out.update(
        {
            "unanswerable_n": len(unanswerable),
            "abstention_correct": rate(
                sum(1 for r in unanswerable if r.scores.abstention_correct), len(unanswerable)
            ),
            "hallucinated": rate(
                sum(1 for r in unanswerable if r.scores.hallucinated), len(unanswerable)
            ),
            "mean_llm_calls": mean([r.scores.llm_calls for r in records]),
            "latency_ms_p50": float(np.percentile(latencies, 50)) if latencies else None,
            "latency_ms_p95": float(np.percentile(latencies, 95)) if latencies else None,
            "mean_tokens_per_question": mean(tokens),
            "used_web": rate(sum(1 for r in records if r.scores.used_web), len(records)),
        }
    )
    if kinds is None:
        kinds, _ = record_kinds(records)
    out.update(_failure_metrics(records, kinds))
    out["structured_call_fallbacks"] = _fallback_metrics(records)
    return out


def record_kinds(
    records: Sequence[EvalRecord], overrides: Sequence[ErrorReclassification] = ()
) -> tuple[dict[str, list[str]], list[ErrorReclassification]]:
    """Kind of every stored failed attempt per item id, and the overrides applied.

    Kinds come from FailedAttempt.kind, else from the message (ragdocs.eval.failures);
    overrides (already filtered to this run) are applied last.
    """
    prefixes = get_settings().rate_limit_error_prefixes
    out: dict[str, list[str]] = {}
    applied: list[ErrorReclassification] = []
    for r in records:
        out[r.id], used = item_kinds(r.id, r.failed_attempts, prefixes, overrides)
        applied += used
    return out, applied


def _failure_metrics(records: list[EvalRecord], kinds: Mapping[str, list[str]]) -> dict[str, Any]:
    """Failed attempts before success, counted by kind (M11 S1).

    n counts records made after the structured_output_failures field existed (M08), so
    runs made before it show '-'. Counts are recomputed from the stored attempts, not
    read from the stored per-item scores.
    """
    counted = [r for r in records if r.scores.structured_output_failures is not None]
    per_item = [count_kinds(kinds.get(r.id, [])) for r in counted]
    n = len(counted)
    structured = [c["structured_output_failures"] for c in per_item]
    out: dict[str, Any] = {
        field: {"total": sum(c[field] for c in per_item), "n": n} for field in KIND_FIELDS.values()
    }
    out["items_with_structured_output_failures"] = rate(sum(1 for c in structured if c), n)
    return out


def fallbacks_of(result: PipelineResult) -> list[str]:
    """diagnostics["fallbacks"] of a stored result; a missing key means none (M11)."""
    return [str(f) for f in result.diagnostics.get("fallbacks", [])]


def _fallback_metrics(records: list[EvalRecord]) -> dict[str, Any]:
    """Items with at least one structured-call fallback, and occurrences per type."""
    per_item = [fallbacks_of(r.result) for r in records]
    by_type = {t: 0 for t in FALLBACK_TYPES}
    for fallbacks in per_item:
        for f in fallbacks:
            by_type[f] = by_type.get(f, 0) + 1
    return {**rate(sum(1 for f in per_item if f), len(records)), "by_type": by_type}


def _totals(records: list[EvalRecord]) -> dict[str, Any]:
    """Total tokens, calls and per-model breakdown over all generation records."""
    by_model: dict[str, dict[str, int]] = {}
    for r in records:
        for model, u in r.usage.by_model.items():
            entry = by_model.setdefault(
                model, {"input_tokens": 0, "output_tokens": 0, "calls": 0, "usage_missing": 0}
            )
            for key in entry:
                entry[key] += getattr(u, key)
    return {
        "tokens_in": sum(r.usage.tokens_in for r in records),
        "tokens_out": sum(r.usage.tokens_out for r in records),
        "llm_calls": sum(r.scores.llm_calls for r in records),
        "usage_missing": sum(r.usage.usage_missing for r in records),
        "by_model": by_model,
    }


def _judge_info(run_dir: Path, records: list[EvalRecord], ev: EffectiveVerdicts) -> dict[str, Any]:
    """Effective judge version, model, coverage and judge token usage."""
    eligible = [r.id for r in records if r.judge_eligible]
    judged = [i for i in eligible if i in ev.verdicts]
    usage = {"tokens_in": 0, "tokens_out": 0, "calls": 0, "cached": 0}
    path = run_dir / ev.source
    if ev.prompt_version is not None and path.is_file():
        for row in read_jsonl(path):
            usage["tokens_in"] += row["usage"]["tokens_in"]
            usage["tokens_out"] += row["usage"]["tokens_out"]
            usage["calls"] += sum(m["calls"] for m in row["usage"]["by_model"].values())
            usage["cached"] += int(bool(row.get("cached")))
    return {
        "effective_prompt_version": ev.prompt_version,
        "judge_model": ev.judge_model,
        "source": ev.source,
        "eligible_n": len(eligible),
        "judged_n": len(judged),
        "complete": len(judged) == len(eligible),
        "usage": usage,
    }


def _extra_scores(records: list[EvalRecord], files: Sequence[Path]) -> dict[str, Any]:
    """Mean of every numeric field in each extra {id, metric...} JSONL file."""
    ids = {r.id for r in records}
    extra: dict[str, Any] = {}
    for f in files:
        rows = [row for row in read_jsonl(f) if row.get("id") in ids]
        metrics = sorted({k for row in rows for k in row if k != "id"})
        extra[Path(f).stem] = {
            m: mean([float(row[m]) for row in rows if isinstance(row.get(m), int | float)])
            for m in metrics
        }
    return extra


def _merge_ragas(run_dir: Path, summary: dict[str, Any]) -> None:
    """Add ragas_<metric> {"mean", "n", "errored"} fields from ragas_summary.json, if present."""
    path = run_dir / RAGAS_SUMMARY_FILE
    if not path.is_file():
        return
    ragas = read_json(path)
    for m in RAGAS_METRICS:
        s = ragas["metrics"][m]
        summary["overall"][f"ragas_{m}"] = {
            "mean": s["mean"],
            "n": s["n_scored"],
            "errored": s["n_errored"],
        }
        for cat, per in ragas["per_category"].items():
            if m in per and cat in summary["per_category"]:
                summary["per_category"][cat][f"ragas_{m}"] = {
                    "mean": per[m]["mean"],
                    "n": per[m]["n_scored"],
                }
    summary["has_ragas"] = True


def rows_for(summaries: Sequence[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """SUMMARY_ROWS plus RAGAS_ROWS when any summary has RAGAS scores."""
    return SUMMARY_ROWS + (RAGAS_ROWS if any(s.get("has_ragas") for s in summaries) else [])


def summarize(run_dir: Path, extra_score_files: Sequence[Path] = ()) -> dict[str, Any]:
    """Return the summary dict for a run folder."""
    run_dir = Path(run_dir)
    records = load_records(run_dir)
    ev = effective_verdicts(run_dir, records)
    config_path = run_dir / "config.json"
    config = read_json(config_path) if config_path.is_file() else {}
    overrides = overrides_for_run(load_overrides(overrides_path(get_settings())), run_dir)
    kinds, applied = record_kinds(records, overrides)
    by_cat = {c: [r for r in records if r.category == c] for c in CATEGORIES}
    summary: dict[str, Any] = {
        "run": run_dir.name,
        "pipeline": config.get("pipeline"),
        "eval_set_sha256": config.get("eval_set_sha256"),
        "index_manifest_hash": config.get("index_manifest_hash"),
        "tracing_enabled": config.get("tracing_enabled"),
        "judge": _judge_info(run_dir, records, ev),
        "overall": _metrics(records, ev, kinds),
        "per_category": {c: _metrics(by_cat[c], ev, kinds) for c in CATEGORIES},
        "totals": _totals(records),
    }
    if applied:
        summary["error_reclassifications"] = [o.model_dump(mode="json") for o in applied]
    _merge_ragas(run_dir, summary)
    if extra_score_files:
        summary["extra"] = _extra_scores(records, extra_score_files)
    return summary


# Row label, key, formatter kind. Shared by summary.md and compare_runs.
SUMMARY_ROWS: list[tuple[str, str, str]] = [
    ("items", "n", "int"),
    ("answerable n", "answerable_n", "int"),
    ("correct (correctness = 2)", "correct", "rate"),
    ("correct or partial (correctness >= 1)", "correct_or_partial", "rate"),
    ("mean correctness (0-2)", "mean_correctness", "mean"),
    ("citation_support (judged items)", "citation_support", "rate"),
    ("first-retrieval hit@5 (like-for-like retrieval)", "first_retrieval_hit@5", "rate"),
    (f"context_hit@5 ({CONTEXT_LABEL})", "context_hit@5", "rate"),
    (f"mean context_evidence_recall@5 ({CONTEXT_LABEL})", "context_evidence_recall@5", "mean"),
    ("mean must_mention coverage (soft signal, D15)", "must_mention_coverage", "mean"),
    ("false_abstention", "false_abstention", "rate"),
    ("abstention_correct (unanswerable)", "abstention_correct", "rate"),
    ("hallucinated (unanswerable)", "hallucinated", "rate"),
    ("mean llm_calls", "mean_llm_calls", "mean"),
    ("p50 latency_ms", "latency_ms_p50", "ms"),
    ("p95 latency_ms", "latency_ms_p95", "ms"),
    ("mean tokens per question", "mean_tokens_per_question", "mean"),
    ("used_web", "used_web", "rate"),
    (
        "structured_output_failures (failed attempts before success)",
        "structured_output_failures",
        "total",
    ),
    (
        "items with >= 1 structured_output failure",
        "items_with_structured_output_failures",
        "rate",
    ),
    ("rate-limited attempts (not counted above)", "rate_limited_attempts", "total"),
    # M11 S1: the other failed-attempt kinds and self-RAG structured-call fallbacks.
    (
        "transient call errors (connection, timeout, 5xx; not counted above)",
        "transient_call_errors",
        "total",
    ),
    (
        "permanent call errors (auth, plan limit, other 4xx; not counted above)",
        "permanent_call_errors",
        "total",
    ),
    ("unclassified call errors (not counted above)", "unclassified_call_errors", "total"),
    ("structured-call fallbacks", "structured_call_fallbacks", "fallbacks"),
]


def format_cell(metrics: dict[str, Any], key: str, kind: str) -> str:
    """Format one summary field for Markdown."""
    value = metrics.get(key)
    if value is None:
        return "-"
    if kind == "rate":
        return format_rate(value)
    if kind == "mean":
        return format_mean(value)
    if kind == "ms":
        return f"{value:.0f} ms"
    if kind == "total":
        return f"{value['total']} (n={value['n']})" if value["n"] else "-"
    if kind == "ragas":
        return "-" if value["mean"] is None else f"{value['mean']:.3f} ({value['n']})"
    if kind == "fallbacks":
        return format_fallbacks(value)
    return str(value)


def format_fallbacks(value: dict[str, Any]) -> str:
    """'rate (count/n)', then occurrences per type when any item had a fallback."""
    text = format_rate(value)
    if value["count"]:
        text += "; " + ", ".join(f"{t} {c}" for t, c in value["by_type"].items())
    return text


def reclassification_notes(summaries: Sequence[dict[str, Any]]) -> list[str]:
    """Footnote lines for every summary whose failure counts use an override."""
    lines: list[str] = []
    for s in summaries:
        for o in s.get("error_reclassifications", []):
            evidence = "; ".join(o["evidence"])
            lines.append(
                f"- Note: {s['run']} {o['item']}: failed-attempt kind set to {o['kind']} by "
                f"{RECLASSIFICATIONS_LABEL} (the stored message cannot show it). "
                f"Evidence: {evidence}."
            )
    return lines


def _judge_lines(judge: dict[str, Any]) -> list[str]:
    """Describe the effective judge and warn when judging is incomplete."""
    version = judge["effective_prompt_version"]
    lines = [
        f"Judge: {judge['judge_model'] or 'none'}, prompt version "
        f"{version if version is not None else 'n/a'} (source {judge['source']}), "
        f"judged {judge['judged_n']}/{judge['eligible_n']} eligible items.",
    ]
    if not judge["complete"]:
        lines.append(
            f"WARNING: judging incomplete ({judge['eligible_n'] - judge['judged_n']} eligible "
            "items unjudged). Correctness fields are lower bounds; run "
            "`py tasks.py judge --run-dir <run>`."
        )
    return lines


def _category_table(per_category: dict[str, Any], rows: list[tuple[str, str, str]]) -> list[str]:
    """Markdown table with one column per category."""
    header = "| Field | " + " | ".join(CATEGORIES) + " |"
    lines = [header, "|---|" + "---|" * len(CATEGORIES)]
    for label, key, kind in rows:
        cells = [format_cell(per_category[c], key, kind) for c in CATEGORIES]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


def render_markdown(summary: dict[str, Any]) -> str:
    """Render summary.md: overall fields, per-category table, totals."""
    overall = summary["overall"]
    totals = summary["totals"]
    lines = [f"# Run summary: {summary['run']}", ""]
    lines += [f"Pipeline: {summary['pipeline']}. Tracing enabled: {summary['tracing_enabled']}."]
    lines += _judge_lines(summary["judge"]) + [""]
    lines += [
        "Rates are shown as rate (count/n). Correctness uses n = every answerable item;",
        "a false abstention counts as correctness 0.",
        "",
    ]
    rows = rows_for([summary])
    lines += ["## Overall", "", "| Field | Value |", "|---|---|"]
    lines += [f"| {lab} | {format_cell(overall, key, kind)} |" for lab, key, kind in rows]
    notes = reclassification_notes([summary])
    lines += ["", *notes] if notes else []
    lines += ["", "## Per category", ""] + _category_table(summary["per_category"], rows)
    lines += ["", "## Totals (generation)", ""]
    lines += [
        f"- Tokens in: {totals['tokens_in']}; tokens out: {totals['tokens_out']}; "
        f"LLM calls: {totals['llm_calls']}; calls without usage data: "
        f"{totals['usage_missing']}"
    ]
    for model, u in sorted(totals["by_model"].items()):
        lines.append(
            f"- {model}: {u['input_tokens']} in, {u['output_tokens']} out, {u['calls']} calls"
        )
    ju = summary["judge"]["usage"]
    lines.append(
        f"- Judge: {ju['tokens_in']} in, {ju['tokens_out']} out, {ju['calls']} calls, "
        f"{ju['cached']} cached verdicts"
    )
    return "\n".join(lines) + "\n"


def write_summary(run_dir: Path, extra_score_files: Sequence[Path] = ()) -> dict[str, Any]:
    """Write summary.json and summary.md into the run folder and return the summary."""
    run_dir = Path(run_dir)
    summary = summarize(run_dir, extra_score_files)
    write_json(run_dir / "summary.json", summary)
    write_text(run_dir / "summary.md", render_markdown(summary))
    return summary
