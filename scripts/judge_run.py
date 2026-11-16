"""Judge the stored answers of a run with the custom LLM judge (M08, D9).

Usage:
    py tasks.py judge --run-dir DIR

Inputs: <run-dir>/per_question.jsonl, Settings.judge_model and judge_prompt_version.
Outputs: <run-dir>/judge_v<N>.jsonl (appended, resumable), summary.json and
summary.md rewritten at the end. Never modifies per_question.jsonl. After a judge
prompt version bump, the same command re-judges into a new judge_v<N>.jsonl.
Exit codes: 0 done, 3 paused at the judge's daily limit or after repeated failures.
"""

import argparse
import sys
from pathlib import Path

from ragdocs.eval.judge_run import run_judge


def main() -> int:
    """Parse arguments and run the judge pass."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True, help="Run folder")
    args = parser.parse_args()
    return run_judge(args.run_dir)


if __name__ == "__main__":
    sys.exit(main())
