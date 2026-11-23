"""Label every failed item of every pipeline and write the review file (M15).

Usage:
    .venv/Scripts/python scripts/failure_breakdown.py

Inputs: results/summary.md (run names), each run's per_question.jsonl, judge_v<N>.jsonl,
ragas_scores.jsonl, and data/index/chunk_meta.jsonl.
Outputs: results/failure_labels.csv (one row per failed item with an automatic or proposed
label) and results/failure_review.md (one section per row, for the human to decide).
No network and no LLM calls; the output is deterministic.
"""

import sys

from ragdocs.config import get_settings
from ragdocs.eval.failure_review import collect_cases, write_outputs
from ragdocs.eval.readme_results import default_inputs


def main() -> int:
    """Write the CSV and the review file."""
    settings = get_settings()
    cases = collect_cases(default_inputs(settings).run_dirs)
    csv_path, md_path = write_outputs(cases, settings.results_dir)
    pending = sum(1 for c in cases if not c.final_label)
    print(f"Wrote {csv_path.name} and {md_path.name}: {len(cases)} rows, {pending} needs_label")
    return 0


if __name__ == "__main__":
    sys.exit(main())
