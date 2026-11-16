"""Generate and score answers for every eval item with one pipeline (M08).

Usage:
    py tasks.py eval --pipeline baseline [--run-dir DIR]

Inputs: data/eval/eval_set.jsonl (frozen at eval-set-v1), data/index/, .env.
Outputs: <run-dir>/config.json (written first), per_question.jsonl (one line per
item, appended), summary.json and summary.md (at the end). Default run dir:
results/runs/<pipeline>-YYYYMMDD-HHMM (UTC). The judge is not called here; run
`py tasks.py judge --run-dir DIR` afterwards.
Exit codes: 0 done, 3 paused at a daily limit or after repeated item failures
(re-run with the same --run-dir to resume).
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from ragdocs.config import get_settings
from ragdocs.eval.runner import EvalSetMismatch, run_eval


def main() -> int:
    """Parse arguments and run the evaluation."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pipeline", required=True, help="Pipeline name, e.g. baseline")
    parser.add_argument("--run-dir", type=Path, default=None, help="Run folder (resume)")
    args = parser.parse_args()
    settings = get_settings()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    run_dir = args.run_dir or settings.results_dir / "runs" / f"{args.pipeline}-{stamp}"
    print(f"Run dir: {Path(run_dir).as_posix()}")
    try:
        return run_eval(args.pipeline, run_dir, settings=settings)
    except EvalSetMismatch as exc:
        print(f"Refusing to run: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
