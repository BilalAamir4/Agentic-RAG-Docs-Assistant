"""Export ragas_input.jsonl, then run tools/ragas_score.py in .venv-ragas (M09, D19 path A).

Usage:
    py tasks.py ragas --run-dir DIR [--out-dir DIR] [--ids q001,q002] [--plan-only] [--cache-check]

Inputs: <run>/per_question.jsonl, Settings (models, limits), GOOGLE_API_KEY via Settings.
Outputs: <run>/ragas_input.jsonl, then ragas_config.json, ragas_scores.jsonl and
ragas_summary.json in --out-dir (default: the run folder). Exit code is the scorer's
(0 done, 1 error, 3 paused on a daily limit; rerun to continue from cache/ragas).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ragdocs.config import REPO_ROOT, get_settings
from ragdocs.eval.ragas_export import (
    RAGAS_FAITHFULNESS_AUDIT,
    RAGAS_TOOL,
    export_ragas_input,
    ragas_python,
    ragas_tool_args,
    ragas_tool_env,
)


def git_commit() -> str:
    """Current HEAD commit, or empty when git is unavailable."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> int:
    """Export, then run the isolated scorer with Settings-derived arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--ids", default="")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--cache-check", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Rescore --ids (probe)")
    parser.add_argument(
        "--faithfulness-audit",
        action="store_true",
        help="Rescore faithfulness for --ids; log to <run>/ragas_faithfulness_audit.jsonl",
    )
    args = parser.parse_args()
    if args.refresh and not args.ids:
        print("--refresh needs --ids", file=sys.stderr)
        return 1
    settings = get_settings()
    python = ragas_python(settings)
    if not python.exists():
        print(f"{python} not found; run: py tasks.py ragas-setup", file=sys.stderr)
        return 1
    input_path, rows = export_ragas_input(args.run_dir)
    print(f"Exported {len(rows)} rows to {input_path.as_posix()}")
    out_dir = args.out_dir or args.run_dir
    cmd = [str(python), str(REPO_ROOT / RAGAS_TOOL)]
    cmd += ragas_tool_args(settings, input_path, out_dir, git_commit())
    if args.ids:
        cmd += ["--ids", args.ids]
    if args.plan_only:
        cmd.append("--plan-only")
    if args.cache_check:
        cmd.append("--cache-check")
    if args.refresh:
        cmd.append("--refresh")
    if args.faithfulness_audit:
        cmd += ["--faithfulness-audit", (out_dir / RAGAS_FAITHFULNESS_AUDIT).as_posix()]
    env = ragas_tool_env(settings, dict(os.environ))
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
