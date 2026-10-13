"""CLI script to validate the evaluation dataset.

Usage:
    .venv/Scripts/python scripts/validate_eval.py [--require-verified]
"""

import argparse
import sys
from pathlib import Path

from ragdocs.eval.validate import validate_eval_dataset
from ragdocs.io_utils import read_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_PATH = REPO_ROOT / "data" / "eval" / "eval_set.jsonl"
DEFAULT_CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "chunks.jsonl"


def run_validation(
    eval_path: Path,
    chunks_path: Path,
    require_verified: bool = False,
) -> int:
    """Read dataset and chunks, run validation, and print report."""
    if not eval_path.exists():
        print(f"Error: eval file not found at {eval_path}", file=sys.stderr)
        return 1

    if not chunks_path.exists():
        print(f"Error: chunks file not found at {chunks_path}", file=sys.stderr)
        return 1

    # Read with utf-8-sig so BOM from Windows editors does not break parsing
    with open(eval_path, encoding="utf-8-sig") as f:
        raw_lines = f.readlines()

    chunks = read_jsonl(chunks_path)

    report = validate_eval_dataset(
        raw_lines=raw_lines,
        chunks=chunks,
        require_verified=require_verified,
    )

    print(report.format_summary())
    return 0 if report.passed else 1


def main() -> int:
    """Parse CLI arguments and run validation."""
    parser = argparse.ArgumentParser(description="Validate evaluation dataset.")
    parser.add_argument(
        "--eval-path",
        default=str(DEFAULT_EVAL_PATH),
        help="Path to eval_set.jsonl",
    )
    parser.add_argument(
        "--chunks-path",
        default=str(DEFAULT_CHUNKS_PATH),
        help="Path to chunks.jsonl",
    )
    parser.add_argument(
        "--require-verified",
        action="store_true",
        help="Require all items to have verified=True",
    )

    args = parser.parse_args()
    return run_validation(
        eval_path=Path(args.eval_path),
        chunks_path=Path(args.chunks_path),
        require_verified=args.require_verified,
    )


if __name__ == "__main__":
    sys.exit(main())
