"""Compare eval runs side by side and write results/summary.md (M08).

Usage:
    py tasks.py compare RUN_DIR [RUN_DIR ...]

Inputs: each run folder's config.json, per_question.jsonl and judge_v<N>.jsonl.
Outputs: results/summary.md with one column per run, per-category tables and a
"Changed questions" list against the first run. Refuses runs with differing eval_set
sha256, index manifest hash, tracing_enabled, effective judge_prompt_version or
judge model.
"""

import argparse
import sys
from pathlib import Path

from ragdocs.config import get_settings
from ragdocs.eval.compare import IncomparableRuns, render_comparison
from ragdocs.io_utils import write_text


def main() -> int:
    """Parse arguments and write the comparison."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dirs", nargs="+", type=Path, help="Run folders; first is the base")
    args = parser.parse_args()
    try:
        content = render_comparison(args.run_dirs)
    except IncomparableRuns as exc:
        print(f"Refusing to compare: {exc}", file=sys.stderr)
        return 1
    out = get_settings().results_dir / "summary.md"
    write_text(out, content)
    print(f"Wrote {out.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
