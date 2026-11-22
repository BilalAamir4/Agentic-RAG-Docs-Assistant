"""Export the three pipeline summaries for the web page (M13).

Usage:
    .venv/Scripts/python scripts/export_results.py [RUN_DIR ...]

Inputs: run folders. With no arguments, the run names in the header row of the first table
of results/summary.md (baseline, corrective, self_rag, in that order), under results/runs/.
Outputs: web/public/results.json with 14 metrics per pipeline, from
ragdocs.eval.report.summarize (which applies the effective judge version). Nothing is
computed here except the fraction-to-integer conversion of counts.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ragdocs.eval.report import summarize
from ragdocs.io_utils import read_text, write_text

REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_MD = REPO_ROOT / "results" / "summary.md"
OUT_PATH = REPO_ROOT / "web" / "public" / "results.json"
PIPELINES = (
    ("baseline", "Baseline RAG"),
    ("corrective", "Corrective RAG"),
    ("self_rag", "Self-RAG"),
)

# (key, label, kind, unit, summarize() field). Order is the display order.
METRICS: list[tuple[str, str, str, str | None, str]] = [
    ("correct", "Correct answers", "rate", None, "correct"),
    ("correct_or_partial", "Correct or partial", "rate", None, "correct_or_partial"),
    ("citation_support", "Citation support", "rate", None, "citation_support"),
    (
        "abstention_correct",
        "Unanswerable correctly declined",
        "rate",
        None,
        "abstention_correct",
    ),
    ("hallucinated", "Hallucinated on unanswerable", "rate", None, "hallucinated"),
    (
        "first_retrieval_hit_at_5",
        "First-retrieval hit@5 (like-for-like retrieval)",
        "rate",
        None,
        "first_retrieval_hit@5",
    ),
    (
        "context_hit_at_5",
        "Context hit@5 (on contexts given to the generator)",
        "rate",
        None,
        "context_hit@5",
    ),
    ("ragas_faithfulness", "RAGAS faithfulness", "mean", None, "ragas_faithfulness"),
    (
        "ragas_response_relevancy",
        "RAGAS response relevancy",
        "mean",
        None,
        "ragas_response_relevancy",
    ),
    (
        "ragas_context_precision",
        "RAGAS context precision (on contexts given to the generator)",
        "mean",
        None,
        "ragas_context_precision",
    ),
    (
        "ragas_context_recall",
        "RAGAS context recall (on contexts given to the generator)",
        "mean",
        None,
        "ragas_context_recall",
    ),
    ("mean_llm_calls", "Mean LLM calls per question", "number", "calls", "mean_llm_calls"),
    (
        "mean_tokens",
        "Mean tokens per question",
        "number",
        "tokens",
        "mean_tokens_per_question",
    ),
    ("p50_latency_ms", "Median latency", "number", "ms", "latency_ms_p50"),
]


def run_dirs_from_summary(summary_md: Path = SUMMARY_MD) -> list[Path]:
    """Return the run folders named in the header row of the first table of summary.md."""
    for line in read_text(summary_md).splitlines():
        if line.startswith("| Field |"):
            names = [c.strip() for c in line.strip("|").split("|")[1:]]
            return [REPO_ROOT / "results" / "runs" / name for name in names]
    raise SystemExit(f"No table header row found in {summary_md}")


def metric_entry(overall: dict[str, Any], spec: tuple[str, str, str, str | None, str]) -> dict:
    """Build one metric object from a summarize() overall dict; fails if the field is absent."""
    key, label, kind, unit, field = spec
    if field not in overall:
        raise SystemExit(f"summarize() has no field {field!r} (needed for {key})")
    raw = overall[field]
    if kind == "rate":
        value, count, n = raw["rate"], raw["count"], raw["n"]
        count = None if count is None else int(count)
    elif kind == "mean":
        value, count, n = raw["mean"], None, raw["n"]
    else:
        # A mean dict (mean_llm_calls, mean_tokens_per_question) or a bare number (percentile).
        value, count = (raw["mean"], None) if isinstance(raw, dict) else (raw, None)
        n = raw["n"] if isinstance(raw, dict) else overall["n"]
    return {"label": label, "value": value, "count": count, "n": n, "kind": kind, "unit": unit}


def build_results(run_dirs: list[Path]) -> dict[str, Any]:
    """Return the results.json content for run folders in pipeline order."""
    pipelines: list[dict[str, Any]] = []
    eval_hash = None
    n_questions = None
    for (name, label), run_dir in zip(PIPELINES, run_dirs, strict=True):
        summary = summarize(run_dir)
        if summary["pipeline"] != name:
            raise SystemExit(f"{run_dir} is pipeline {summary['pipeline']!r}, expected {name!r}")
        eval_hash = eval_hash or summary["eval_set_sha256"]
        n_questions = summary["overall"]["n"]
        metrics = {s[0]: metric_entry(summary["overall"], s) for s in METRICS}
        pipelines.append(
            {
                "name": name,
                "label": label,
                "run_dir": run_dir.relative_to(REPO_ROOT).as_posix(),
                "metrics": metrics,
            }
        )
    return {
        "generated_on": date.today().isoformat(),
        "n_questions": n_questions,
        "eval_set_sha256": eval_hash,
        "pipelines": pipelines,
    }


def main() -> int:
    """Write web/public/results.json."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dirs", nargs="*", type=Path, help="Run folders, in pipeline order")
    args = parser.parse_args()
    dirs = [d.resolve() for d in args.run_dirs] or run_dirs_from_summary()
    data = build_results(dirs)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_text(OUT_PATH, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
