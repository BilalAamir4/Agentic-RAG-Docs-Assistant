"""Render or check the README results block (M15).

Usage:
    .venv/Scripts/python scripts/render_readme_results.py [--write | --check]

Inputs: results/summary.md (run names), the three pipeline run folders, the retrieval
ablation run, data/index/manifest.json and results/judge_audit.md. Nothing else.
Outputs: README.md, between <!-- results:start --> and <!-- results:end -->. --write
(the default) replaces the block; --check exits 1 with a unified diff when the block is
out of date or the markers are missing.
"""

import argparse
import sys

from ragdocs.config import REPO_ROOT
from ragdocs.eval.readme_results import default_inputs, run


def main() -> int:
    """Parse arguments and write or check the block."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="Rewrite the block (default)")
    group.add_argument("--check", action="store_true", help="Fail if the block is out of date")
    args = parser.parse_args()
    return run(REPO_ROOT / "README.md", default_inputs(), check=args.check)


if __name__ == "__main__":
    sys.exit(main())
